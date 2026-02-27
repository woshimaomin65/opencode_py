"""
Storage module for OpenCode Store.

Provides storage management functionality:
- Storage directory management and initialization
- File-based storage with locking
- Storage migrations
- JSON file read/write operations
"""

import os
import json
import logging
import asyncio
from pathlib import Path
from typing import Any, Callable, TypeVar, Optional, List
from contextlib import asynccontextmanager, contextmanager

from filelock import AsyncFileLock, FileLock

from opencode.store.db import Database
from opencode.store.migration import run_json_migration

logger = logging.getLogger(__name__)


T = TypeVar('T')


class StorageNotFoundError(Exception):
    """Raised when a storage resource is not found."""
    
    def __init__(self, message: str, path: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.path = path


class StorageLock:
    """
    File-based locking for storage operations.
    
    Provides read and write locks to ensure data consistency
    when multiple processes access the same files.
    """
    
    @staticmethod
    @asynccontextmanager
    async def read_lock(path: str):
        """
        Acquire a read lock for a file.
        
        Note: This implementation uses exclusive locks for simplicity.
        For true read-write locks, consider using a more sophisticated
        locking mechanism.
        """
        lock_path = path + ".lock"
        lock = AsyncFileLock(lock_path, timeout=30)
        
        try:
            await asyncio.get_event_loop().run_in_executor(None, lock.acquire)
            yield
        finally:
            await asyncio.get_event_loop().run_in_executor(None, lock.release)
    
    @staticmethod
    @asynccontextmanager
    async def write_lock(path: str):
        """Acquire a write lock for a file."""
        lock_path = path + ".lock"
        lock = AsyncFileLock(lock_path, timeout=30)
        
        try:
            await asyncio.get_event_loop().run_in_executor(None, lock.acquire)
            yield
        finally:
            await asyncio.get_event_loop().run_in_executor(None, lock.release)
    
    @staticmethod
    @contextmanager
    def read_lock_sync(path: str):
        """Synchronous read lock."""
        lock_path = path + ".lock"
        lock = FileLock(lock_path, timeout=30)
        
        try:
            lock.acquire()
            yield
        finally:
            lock.release()
    
    @staticmethod
    @contextmanager
    def write_lock_sync(path: str):
        """Synchronous write lock."""
        lock_path = path + ".lock"
        lock = FileLock(lock_path, timeout=30)
        
        try:
            lock.acquire()
            yield
        finally:
            lock.release()


class Storage:
    """
    Storage manager for file-based and database storage.
    
    Handles:
    - Storage directory initialization
    - Storage migrations
    - JSON file operations with locking
    - Error handling for file operations
    """
    
    _initialized = False
    _storage_dir: Optional[str] = None
    _migration_version: int = 0
    
    # Migration functions
    _migrations: List[Callable[[str], Any]] = []
    
    @classmethod
    def _get_storage_dir(cls) -> str:
        """Get the storage directory path."""
        from opencode.global_path import get_data_path
        return os.path.join(get_data_path(), "storage")
    
    @classmethod
    def _get_migration_file(cls) -> str:
        """Get the migration version file path."""
        return os.path.join(cls._get_storage_dir(), "migration")
    
    @classmethod
    async def _run_migrations(cls) -> None:
        """Run storage migrations."""
        storage_dir = cls._get_storage_dir()
        migration_file = cls._get_migration_file()
        
        # Read current migration version
        current_version = 0
        if os.path.exists(migration_file):
            try:
                with open(migration_file, 'r') as f:
                    current_version = int(f.read().strip())
            except (ValueError, IOError):
                current_version = 0
        
        # Run migrations
        for index in range(current_version, len(cls._migrations)):
            logger.info(f"Running migration {index}")
            try:
                migration_fn = cls._migrations[index]
                if asyncio.iscoroutinefunction(migration_fn):
                    await migration_fn(storage_dir)
                else:
                    migration_fn(storage_dir)
                
                # Update migration version
                with open(migration_file, 'w') as f:
                    f.write(str(index + 1))
                    
            except Exception as e:
                logger.error(f"Failed to run migration {index}: {e}")
    
    @classmethod
    async def initialize(cls) -> str:
        """
        Initialize the storage system.
        
        Creates the storage directory and runs any pending migrations.
        
        Returns:
            The storage directory path
        """
        if cls._initialized:
            return cls._get_storage_dir()
        
        storage_dir = cls._get_storage_dir()
        
        # Create storage directory
        os.makedirs(storage_dir, exist_ok=True)
        
        # Create subdirectories
        for subdir in ["project", "session", "message", "part", "todo", "permission", "session_share"]:
            os.makedirs(os.path.join(storage_dir, subdir), exist_ok=True)
        
        # Run migrations
        await cls._run_migrations()
        
        cls._initialized = True
        logger.info(f"Storage initialized: {storage_dir}")
        
        return storage_dir
    
    @classmethod
    def register_migration(cls, migration_fn: Callable[[str], Any]) -> None:
        """
        Register a migration function.
        
        Args:
            migration_fn: Function that takes storage directory and performs migration
        """
        cls._migrations.append(migration_fn)
    
    @classmethod
    async def remove(cls, key: List[str]) -> None:
        """
        Remove a storage file.
        
        Args:
            key: Path components for the file
        """
        storage_dir = await cls.initialize()
        target = os.path.join(storage_dir, *key) + ".json"
        
        try:
            async with StorageLock.write_lock(target):
                if os.path.exists(target):
                    os.remove(target)
        except FileNotFoundError:
            pass  # File doesn't exist, that's okay
        except Exception as e:
            logger.error(f"Failed to remove {target}: {e}")
    
    @classmethod
    async def read(cls, key: List[str]) -> Any:
        """
        Read a storage file.
        
        Args:
            key: Path components for the file
        
        Returns:
            Parsed JSON content
        
        Raises:
            StorageNotFoundError: If the file doesn't exist
        """
        storage_dir = await cls.initialize()
        target = os.path.join(storage_dir, *key) + ".json"
        
        async with StorageLock.read_lock(target):
            if not os.path.exists(target):
                raise StorageNotFoundError(f"Resource not found: {target}", target)
            
            try:
                with open(target, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from {target}: {e}")
                raise
            except IOError as e:
                if e.errno == 2:  # ENOENT
                    raise StorageNotFoundError(f"Resource not found: {target}", target)
                raise
    
    @classmethod
    async def update(cls, key: List[str], fn: Callable[[Any], None]) -> Any:
        """
        Update a storage file atomically.
        
        Args:
            key: Path components for the file
            fn: Function that modifies the content
        
        Returns:
            Updated content
        
        Raises:
            StorageNotFoundError: If the file doesn't exist
        """
        storage_dir = await cls.initialize()
        target = os.path.join(storage_dir, *key) + ".json"
        
        async with StorageLock.write_lock(target):
            if not os.path.exists(target):
                raise StorageNotFoundError(f"Resource not found: {target}", target)
            
            try:
                with open(target, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                
                fn(content)
                
                with open(target, 'w', encoding='utf-8') as f:
                    json.dump(content, f, indent=2)
                
                return content
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from {target}: {e}")
                raise
            except IOError as e:
                if e.errno == 2:  # ENOENT
                    raise StorageNotFoundError(f"Resource not found: {target}", target)
                raise
    
    @classmethod
    async def write(cls, key: List[str], content: Any) -> None:
        """
        Write to a storage file.
        
        Args:
            key: Path components for the file
            content: Content to write (will be JSON serialized)
        """
        storage_dir = await cls.initialize()
        target = os.path.join(storage_dir, *key) + ".json"
        
        # Ensure parent directory exists
        parent_dir = os.path.dirname(target)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        
        async with StorageLock.write_lock(target):
            try:
                with open(target, 'w', encoding='utf-8') as f:
                    json.dump(content, f, indent=2)
            except IOError as e:
                logger.error(f"Failed to write to {target}: {e}")
                raise
    
    @classmethod
    async def list_files(cls, prefix: List[str]) -> List[List[str]]:
        """
        List files in storage with a given prefix.
        
        Args:
            prefix: Path prefix to search under
        
        Returns:
            List of key paths (without .json extension)
        """
        storage_dir = await cls.initialize()
        search_dir = os.path.join(storage_dir, *prefix)
        
        if not os.path.exists(search_dir):
            return []
        
        try:
            result = []
            for root, dirs, files in os.walk(search_dir):
                for file in files:
                    if file.endswith('.json'):
                        # Get relative path from search_dir
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, search_dir)
                        # Remove .json extension and split into components
                        key_parts = rel_path[:-5].split(os.sep)
                        result.append(prefix + key_parts)
            
            result.sort()
            return result
            
        except Exception as e:
            logger.error(f"Failed to list files in {search_dir}: {e}")
            return []


# Module-level convenience functions

async def read(key: List[str]) -> Any:
    """Read from storage."""
    return await Storage.read(key)


async def write(key: List[str], content: Any) -> None:
    """Write to storage."""
    await Storage.write(key, content)


async def update(key: List[str], fn: Callable[[Any], None]) -> Any:
    """Update storage content."""
    return await Storage.update(key, fn)


async def remove(key: List[str]) -> None:
    """Remove from storage."""
    await Storage.remove(key)


async def list_files(prefix: List[str]) -> List[List[str]]:
    """List files in storage."""
    return await Storage.list_files(prefix)


async def initialize_storage() -> str:
    """Initialize storage system."""
    return await Storage.initialize()
