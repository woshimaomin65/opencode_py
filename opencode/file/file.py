"""
File module for OpenCode.

Handles file operations including:
- Reading and writing files
- File watching
- Path utilities
- File type detection
"""

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any, Optional, AsyncIterator, Callable
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FileInfo:
    """Information about a file."""
    path: Path
    name: str
    size: int
    is_file: bool
    is_dir: bool
    is_symlink: bool
    created_at: datetime
    modified_at: datetime
    accessed_at: datetime
    extension: str
    mime_type: Optional[str] = None


@dataclass
class FileWatchEvent:
    """Event from file watching."""
    event_type: str  # created, modified, deleted, moved
    path: Path
    src_path: Optional[Path] = None  # For move events


async def read_file(path: Path, encoding: str = "utf-8") -> str:
    """
    Read file contents asynchronously.
    
    Args:
        path: File path
        encoding: File encoding
        
    Returns:
        File contents
    """
    path = Path(path)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: path.read_text(encoding=encoding)
    )


async def write_file(path: Path, content: str, encoding: str = "utf-8") -> None:
    """
    Write file contents asynchronously.
    
    Args:
        path: File path
        content: File contents
        encoding: File encoding
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: path.write_text(content, encoding=encoding)
    )


async def read_file_binary(path: Path) -> bytes:
    """
    Read file as binary.
    
    Args:
        path: File path
        
    Returns:
        File contents as bytes
    """
    path = Path(path)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: path.read_bytes()
    )


async def write_file_binary(path: Path, content: bytes) -> None:
    """
    Write file as binary.
    
    Args:
        path: File path
        content: File contents as bytes
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: path.write_bytes(content)
    )


async def file_exists(path: Path) -> bool:
    """Check if file exists."""
    return Path(path).exists()


async def is_file(path: Path) -> bool:
    """Check if path is a file."""
    return Path(path).is_file()


async def is_directory(path: Path) -> bool:
    """Check if path is a directory."""
    return Path(path).is_dir()


async def get_file_info(path: Path) -> Optional[FileInfo]:
    """
    Get file information.
    
    Args:
        path: File path
        
    Returns:
        FileInfo object or None if file doesn't exist
    """
    path = Path(path)
    
    if not path.exists():
        return None
    
    stat = path.stat()
    
    # Simple mime type detection
    mime_type = None
    if path.is_file():
        ext = path.suffix.lower()
        mime_map = {
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".py": "text/x-python",
            ".js": "text/javascript",
            ".ts": "text/typescript",
            ".json": "application/json",
            ".yaml": "application/yaml",
            ".yml": "application/yaml",
            ".xml": "application/xml",
            ".html": "text/html",
            ".css": "text/css",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".gif": "image/gif",
            ".pdf": "application/pdf",
        }
        mime_type = mime_map.get(ext)
    
    return FileInfo(
        path=path,
        name=path.name,
        size=stat.st_size,
        is_file=path.is_file(),
        is_dir=path.is_dir(),
        is_symlink=path.is_symlink(),
        created_at=datetime.fromtimestamp(stat.st_ctime),
        modified_at=datetime.fromtimestamp(stat.st_mtime),
        accessed_at=datetime.fromtimestamp(stat.st_atime),
        extension=path.suffix,
        mime_type=mime_type,
    )


async def list_directory(path: Path, pattern: Optional[str] = None) -> list[Path]:
    """
    List directory contents.
    
    Args:
        path: Directory path
        pattern: Optional glob pattern to filter results
        
    Returns:
        List of file paths
    """
    path = Path(path)
    
    if not path.is_dir():
        return []
    
    if pattern:
        import fnmatch
        return [p for p in path.iterdir() if fnmatch.fnmatch(p.name, pattern)]
    
    return list(path.iterdir())


async def walk_directory(
    path: Path,
    exclude_patterns: Optional[list[str]] = None,
    file_only: bool = False,
    dir_only: bool = False,
) -> AsyncIterator[Path]:
    """
    Walk directory tree asynchronously.
    
    Args:
        path: Root directory path
        exclude_patterns: Patterns to exclude
        file_only: Only yield files
        dir_only: Only yield directories
        
    Yields:
        File or directory paths
    """
    import fnmatch
    
    path = Path(path)
    exclude_patterns = exclude_patterns or []
    
    def should_exclude(p: Path) -> bool:
        for pattern in exclude_patterns:
            if fnmatch.fnmatch(p.name, pattern):
                return True
            if fnmatch.fnmatch(str(p), pattern):
                return True
        return False
    
    def walk(p: Path) -> list[Path]:
        results = []
        try:
            for child in p.iterdir():
                if should_exclude(child):
                    continue
                
                if child.is_dir():
                    if not dir_only:
                        results.append(child)
                    results.extend(walk(child))
                elif child.is_file():
                    if not file_only:
                        results.append(child)
                    else:
                        results.append(child)
        except PermissionError:
            pass
        return results
    
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, lambda: walk(path))
    
    for result in results:
        yield result


async def copy_file(src: Path, dst: Path) -> None:
    """Copy a file."""
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: shutil.copy2(src, dst)
    )


async def copy_directory(src: Path, dst: Path) -> None:
    """Copy a directory recursively."""
    src = Path(src)
    dst = Path(dst)
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: shutil.copytree(src, dst, dirs_exist_ok=True)
    )


async def move_file(src: Path, dst: Path) -> None:
    """Move a file."""
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: shutil.move(src, dst)
    )


async def delete_file(path: Path) -> bool:
    """
    Delete a file.
    
    Returns:
        True if deleted, False if didn't exist
    """
    path = Path(path)
    
    if not path.exists():
        return False
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: path.unlink()
    )
    return True


async def delete_directory(path: Path, recursive: bool = True) -> bool:
    """
    Delete a directory.
    
    Returns:
        True if deleted, False if didn't exist
    """
    path = Path(path)
    
    if not path.exists():
        return False
    
    loop = asyncio.get_event_loop()
    
    if recursive:
        await loop.run_in_executor(
            None,
            lambda: shutil.rmtree(path)
        )
    else:
        await loop.run_in_executor(
            None,
            lambda: path.rmdir()
        )
    return True


async def create_directory(path: Path, parents: bool = True) -> None:
    """Create a directory."""
    path = Path(path)
    
    if parents:
        path.mkdir(parents=True, exist_ok=True)
    else:
        path.mkdir()


async def get_file_lines(path: Path, encoding: str = "utf-8") -> list[str]:
    """
    Get file lines.
    
    Args:
        path: File path
        encoding: File encoding
        
    Returns:
        List of lines
    """
    content = await read_file(path, encoding)
    return content.splitlines()


async def tail_file(path: Path, lines: int = 10, encoding: str = "utf-8") -> list[str]:
    """
    Get last N lines of a file.
    
    Args:
        path: File path
        lines: Number of lines
        encoding: File encoding
        
    Returns:
        Last N lines
    """
    all_lines = await get_file_lines(path, encoding)
    return all_lines[-lines:] if len(all_lines) > lines else all_lines


async def watch_file(
    path: Path,
    callback: Callable[[FileWatchEvent], Any],
    ignore_patterns: Optional[list[str]] = None,
) -> asyncio.Task:
    """
    Watch a file or directory for changes.
    
    Args:
        path: Path to watch
        callback: Callback function for events
        ignore_patterns: Patterns to ignore
        
    Returns:
        asyncio.Task for the watcher
    """
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent, FileMovedEvent
    except ImportError:
        raise ImportError("watchdog package required. Install with: pip install watchdog")
    
    path = Path(path)
    ignore_patterns = ignore_patterns or []
    
    class WatchHandler(FileSystemEventHandler):
        def on_any_event(self, event):
            # Check ignore patterns
            import fnmatch
            for pattern in ignore_patterns:
                if fnmatch.fnmatch(event.src_path, pattern):
                    return
            
            event_type = "modified"
            src_path = None
            
            if isinstance(event, FileCreatedEvent):
                event_type = "created"
            elif isinstance(event, FileDeletedEvent):
                event_type = "deleted"
            elif isinstance(event, FileMovedEvent):
                event_type = "moved"
                src_path = Path(event.src_path)
            
            watch_event = FileWatchEvent(
                event_type=event_type,
                path=Path(event.dest_path if hasattr(event, 'dest_path') else event.src_path),
                src_path=src_path,
            )
            
            if asyncio.iscoroutinefunction(callback):
                asyncio.create_task(callback(watch_event))
            else:
                callback(watch_event)
    
    observer = Observer()
    handler = WatchHandler()
    
    watch_path = path if path.is_dir() else path.parent
    observer.schedule(handler, str(watch_path), recursive=False)
    observer.start()
    
    async def watcher_task():
        try:
            while observer.is_alive():
                await asyncio.sleep(0.1)
        finally:
            observer.stop()
            observer.join()
    
    return asyncio.create_task(watcher_task())


def is_binary(path: Path, sample_size: int = 8192) -> bool:
    """
    Check if file is binary.
    
    Args:
        path: File path
        sample_size: Bytes to sample
        
    Returns:
        True if binary, False if text
    """
    try:
        with open(path, 'rb') as f:
            sample = f.read(sample_size)
        
        if b'\x00' in sample:
            return True
        
        try:
            sample.decode('utf-8')
            return False
        except UnicodeDecodeError:
            return True
            
    except (IOError, PermissionError):
        return True


def get_text_encoding(path: Path) -> str:
    """
    Detect file text encoding.
    
    Returns 'utf-8' for text files, 'binary' for binary files.
    """
    if is_binary(path):
        return 'binary'
    return 'utf-8'
