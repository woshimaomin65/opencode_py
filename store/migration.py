"""
JSON Migration module for OpenCode Store.

Migrates legacy JSON file storage to SQLite database.
Handles:
- Project migration
- Session migration
- Message and Part migration
- Todo, Permission, and Share migration
- Progress tracking
- Error handling and orphan detection
"""

import os
import json
import logging
import time
import glob as glob_module
from pathlib import Path
from typing import Any, Optional, List, Dict, Set, Callable
from dataclasses import dataclass

from sqlalchemy import text

from store.db import Database

logger = logging.getLogger(__name__)


@dataclass
class MigrationProgress:
    """Migration progress information."""
    current: int
    total: int
    label: str


@dataclass
class MigrationStats:
    """Migration statistics."""
    projects: int = 0
    sessions: int = 0
    messages: int = 0
    parts: int = 0
    todos: int = 0
    permissions: int = 0
    shares: int = 0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class JsonMigration:
    """
    JSON to SQLite migration handler.
    
    Migrates legacy JSON file storage to the SQLite database.
    Preserves data integrity and handles edge cases like orphaned records.
    """
    
    BATCH_SIZE = 1000
    
    @classmethod
    def _scan_files(cls, storage_dir: str, pattern: str) -> List[str]:
        """Scan for files matching a pattern."""
        full_pattern = os.path.join(storage_dir, pattern)
        return glob_module.glob(full_pattern, recursive=False)
    
    @classmethod
    def _read_json_files(cls, files: List[str], start: int, end: int) -> List[Optional[dict]]:
        """
        Read a batch of JSON files.
        
        Args:
            files: List of file paths
            start: Start index
            end: End index
        
        Returns:
            List of parsed JSON objects (None for failed reads)
        """
        results = []
        for i in range(start, min(end, len(files))):
            try:
                with open(files[i], 'r', encoding='utf-8') as f:
                    results.append(json.load(f))
            except Exception as e:
                logger.error(f"Failed to read {files[i]}: {e}")
                results.append(None)
        return results
    
    @classmethod
    def _insert_batch(
        cls,
        session: Any,
        values: List[dict],
        table_name: str,
        columns: List[str],
    ) -> int:
        """
        Insert a batch of values into a table.
        
        Args:
            session: Database session
            values: List of value dictionaries
            table_name: Target table name
            columns: Column names
        
        Returns:
            Number of successfully inserted rows
        """
        if not values:
            return 0
        
        try:
            # Build INSERT OR IGNORE statement
            placeholders = ", ".join([f":{col}" for col in columns])
            column_list = ", ".join(columns)
            
            sql = f"""
                INSERT OR IGNORE INTO {table_name} ({column_list})
                VALUES ({placeholders})
            """
            
            session.execute(text(sql), values)
            return len(values)
            
        except Exception as e:
            logger.error(f"Failed to migrate {table_name} batch: {e}")
            return 0
    
    @classmethod
    def run(
        cls,
        progress_callback: Optional[Callable[[MigrationProgress], None]] = None,
    ) -> MigrationStats:
        """
        Run the JSON to SQLite migration.
        
        Args:
            progress_callback: Optional callback for progress updates
        
        Returns:
            Migration statistics
        """
        from global_path import get_data_path
        storage_dir = os.path.join(get_data_path(), "storage")
        
        stats = MigrationStats()
        
        if not os.path.exists(storage_dir):
            logger.info("Storage directory does not exist, skipping migration")
            return stats
        
        logger.info(f"Starting JSON to SQLite migration: {storage_dir}")
        start_time = time.time()
        
        # Optimize SQLite for bulk inserts
        def optimize_sqlite(session):
            session.execute(text("PRAGMA journal_mode = WAL"))
            session.execute(text("PRAGMA synchronous = OFF"))
            session.execute(text("PRAGMA cache_size = 10000"))
            session.execute(text("PRAGMA temp_store = MEMORY"))
        
        Database.use(optimize_sqlite)
        
        now = int(time.time() * 1000)
        
        # Scan all files upfront
        logger.info("Scanning files...")
        
        project_files = cls._scan_files(storage_dir, "project/*.json")
        session_files = cls._scan_files(storage_dir, "session/*/*.json")
        message_files = cls._scan_files(storage_dir, "message/*/*.json")
        part_files = cls._scan_files(storage_dir, "part/*/*.json")
        todo_files = cls._scan_files(storage_dir, "todo/*.json")
        perm_files = cls._scan_files(storage_dir, "permission/*.json")
        share_files = cls._scan_files(storage_dir, "session_share/*.json")
        
        logger.info(f"File scan complete:")
        logger.info(f"  Projects: {len(project_files)}")
        logger.info(f"  Sessions: {len(session_files)}")
        logger.info(f"  Messages: {len(message_files)}")
        logger.info(f"  Parts: {len(part_files)}")
        logger.info(f"  Todos: {len(todo_files)}")
        logger.info(f"  Permissions: {len(perm_files)}")
        logger.info(f"  Shares: {len(share_files)}")
        
        total = max(1, sum([
            len(project_files),
            len(session_files),
            len(message_files),
            len(part_files),
            len(todo_files),
            len(perm_files),
            len(share_files),
        ]))
        
        current = 0
        
        def report_progress(label: str, count: int):
            nonlocal current
            current = min(total, current + count)
            if progress_callback:
                progress_callback(MigrationProgress(current=current, total=total, label=label))
        
        if progress_callback:
            progress_callback(MigrationProgress(current=0, total=total, label="starting"))
        
        # Track orphaned records
        orphans = {
            "sessions": 0,
            "todos": 0,
            "permissions": 0,
            "shares": 0,
        }
        
        # Track IDs for referential integrity
        project_ids: Set[str] = set()
        session_ids: Set[str] = set()
        message_sessions: Dict[str, str] = {}  # message_id -> session_id
        
        def migrate_projects(session):
            """Migrate project files."""
            logger.info("Migrating projects...")
            
            for i in range(0, len(project_files), cls.BATCH_SIZE):
                end = min(i + cls.BATCH_SIZE, len(project_files))
                batch = cls._read_json_files(project_files, i, end)
                
                values = []
                for j, data in enumerate(batch):
                    if not data:
                        continue
                    
                    file_path = project_files[i + j]
                    file_id = os.path.basename(file_path)[:-5]  # Remove .json
                    
                    project_ids.add(file_id)
                    
                    values.append({
                        "id": file_id,
                        "worktree": data.get("worktree", "/"),
                        "vcs": data.get("vcs"),
                        "name": data.get("name"),
                        "icon_url": data.get("icon", {}).get("url") if data.get("icon") else None,
                        "icon_color": data.get("icon", {}).get("color") if data.get("icon") else None,
                        "time_created": data.get("time", {}).get("created", now),
                        "time_updated": data.get("time", {}).get("updated", now),
                        "time_initialized": data.get("time", {}).get("initialized"),
                        "sandboxes": json.dumps(data.get("sandboxes", [])),
                        "commands": json.dumps(data.get("commands")),
                    })
                
                count = cls._insert_batch(
                    session, values, "project",
                    ["id", "worktree", "vcs", "name", "icon_url", "icon_color",
                     "time_created", "time_updated", "time_initialized", "sandboxes", "commands"]
                )
                stats.projects += count
                report_progress("projects", end - i)
            
            logger.info(f"Migrated {stats.projects} projects")
        
        def migrate_sessions(session):
            """Migrate session files."""
            logger.info("Migrating sessions...")
            
            # Extract project IDs from file paths
            session_projects = [
                os.path.basename(os.path.dirname(f)) for f in session_files
            ]
            
            for i in range(0, len(session_files), cls.BATCH_SIZE):
                end = min(i + cls.BATCH_SIZE, len(session_files))
                batch = cls._read_json_files(session_files, i, end)
                
                values = []
                for j, data in enumerate(batch):
                    if not data:
                        continue
                    
                    file_path = session_files[i + j]
                    file_id = os.path.basename(file_path)[:-5]  # Remove .json
                    project_id = session_projects[i + j]
                    
                    if project_id not in project_ids:
                        orphans["sessions"] += 1
                        continue
                    
                    session_ids.add(file_id)
                    
                    summary = data.get("summary", {})
                    time_data = data.get("time", {})
                    
                    values.append({
                        "id": file_id,
                        "project_id": project_id,
                        "parent_id": data.get("parentID"),
                        "slug": data.get("slug", ""),
                        "directory": data.get("directory", ""),
                        "title": data.get("title", ""),
                        "version": data.get("version", ""),
                        "share_url": data.get("share", {}).get("url") if data.get("share") else None,
                        "summary_additions": summary.get("additions"),
                        "summary_deletions": summary.get("deletions"),
                        "summary_files": summary.get("files"),
                        "summary_diffs": json.dumps(summary.get("diffs")) if summary.get("diffs") else None,
                        "revert": json.dumps(data.get("revert")) if data.get("revert") else None,
                        "permission": json.dumps(data.get("permission")) if data.get("permission") else None,
                        "time_created": time_data.get("created", now),
                        "time_updated": time_data.get("updated", now),
                        "time_compacting": time_data.get("compacting"),
                        "time_archived": time_data.get("archived"),
                    })
                
                count = cls._insert_batch(
                    session, values, "session",
                    ["id", "project_id", "parent_id", "slug", "directory", "title", "version",
                     "share_url", "summary_additions", "summary_deletions", "summary_files",
                     "summary_diffs", "revert", "permission", "time_created", "time_updated",
                     "time_compacting", "time_archived"]
                )
                stats.sessions += count
                report_progress("sessions", end - i)
            
            logger.info(f"Migrated {stats.sessions} sessions")
            if orphans["sessions"] > 0:
                logger.warning(f"Skipped {orphans['sessions']} orphaned sessions")
        
        def migrate_messages(session):
            """Migrate message files."""
            logger.info("Migrating messages...")
            
            # Filter messages by valid sessions
            valid_message_files = []
            valid_message_sessions = []
            
            for file_path in message_files:
                session_id = os.path.basename(os.path.dirname(file_path))
                if session_id in session_ids:
                    valid_message_files.append(file_path)
                    valid_message_sessions.append(session_id)
            
            for i in range(0, len(valid_message_files), cls.BATCH_SIZE):
                end = min(i + cls.BATCH_SIZE, len(valid_message_files))
                batch = cls._read_json_files(valid_message_files, i, end)
                
                values = []
                for j, data in enumerate(batch):
                    if not data:
                        continue
                    
                    file_path = valid_message_files[i + j]
                    file_id = os.path.basename(file_path)[:-5]  # Remove .json
                    session_id = valid_message_sessions[i + j]
                    
                    message_sessions[file_id] = session_id
                    
                    # Remove id and sessionID from data
                    data_copy = {k: v for k, v in data.items() if k not in ["id", "sessionID"]}
                    time_data = data.get("time", {})
                    
                    values.append({
                        "id": file_id,
                        "session_id": session_id,
                        "time_created": time_data.get("created", now),
                        "data": json.dumps(data_copy),
                    })
                
                count = cls._insert_batch(
                    session, values, "message",
                    ["id", "session_id", "time_created", "data"]
                )
                stats.messages += count
                report_progress("messages", end - i)
            
            logger.info(f"Migrated {stats.messages} messages")
        
        def migrate_parts(session):
            """Migrate part files."""
            logger.info("Migrating parts...")
            
            for i in range(0, len(part_files), cls.BATCH_SIZE):
                end = min(i + cls.BATCH_SIZE, len(part_files))
                batch = cls._read_json_files(part_files, i, end)
                
                values = []
                for j, data in enumerate(batch):
                    if not data:
                        continue
                    
                    file_path = part_files[i + j]
                    file_id = os.path.basename(file_path)[:-5]  # Remove .json
                    message_id = os.path.basename(os.path.dirname(file_path))
                    session_id = message_sessions.get(message_id)
                    
                    if not session_id:
                        stats.errors.append(f"Part missing message session: {file_path}")
                        continue
                    
                    if session_id not in session_ids:
                        continue
                    
                    # Remove id, messageID, sessionID from data
                    data_copy = {k: v for k, v in data.items() if k not in ["id", "messageID", "sessionID"]}
                    time_data = data.get("time", {})
                    
                    values.append({
                        "id": file_id,
                        "message_id": message_id,
                        "session_id": session_id,
                        "time_created": time_data.get("created", now),
                        "data": json.dumps(data_copy),
                    })
                
                count = cls._insert_batch(
                    session, values, "part",
                    ["id", "message_id", "session_id", "time_created", "data"]
                )
                stats.parts += count
                report_progress("parts", end - i)
            
            logger.info(f"Migrated {stats.parts} parts")
        
        def migrate_todos(session):
            """Migrate todo files."""
            logger.info("Migrating todos...")
            
            todo_sessions = [os.path.basename(f)[:-5] for f in todo_files]
            
            for i in range(0, len(todo_files), cls.BATCH_SIZE):
                end = min(i + cls.BATCH_SIZE, len(todo_files))
                batch = cls._read_json_files(todo_files, i, end)
                
                values = []
                for j, data in enumerate(batch):
                    if not data:
                        continue
                    
                    session_id = todo_sessions[i + j]
                    
                    if session_id not in session_ids:
                        orphans["todos"] += 1
                        continue
                    
                    if not isinstance(data, list):
                        stats.errors.append(f"Todo not an array: {todo_files[i + j]}")
                        continue
                    
                    for position, todo in enumerate(data):
                        if not todo or not todo.get("content") or not todo.get("status") or not todo.get("priority"):
                            continue
                        
                        values.append({
                            "session_id": session_id,
                            "content": todo["content"],
                            "status": todo["status"],
                            "priority": todo["priority"],
                            "position": position,
                            "time_created": now,
                            "time_updated": now,
                        })
                
                count = cls._insert_batch(
                    session, values, "todo",
                    ["session_id", "content", "status", "priority", "position", "time_created", "time_updated"]
                )
                stats.todos += count
                report_progress("todos", end - i)
            
            logger.info(f"Migrated {stats.todos} todos")
            if orphans["todos"] > 0:
                logger.warning(f"Skipped {orphans['todos']} orphaned todos")
        
        def migrate_permissions(session):
            """Migrate permission files."""
            logger.info("Migrating permissions...")
            
            perm_projects = [os.path.basename(f)[:-5] for f in perm_files]
            
            for i in range(0, len(perm_files), cls.BATCH_SIZE):
                end = min(i + cls.BATCH_SIZE, len(perm_files))
                batch = cls._read_json_files(perm_files, i, end)
                
                values = []
                for j, data in enumerate(batch):
                    if not data:
                        continue
                    
                    project_id = perm_projects[i + j]
                    
                    if project_id not in project_ids:
                        orphans["permissions"] += 1
                        continue
                    
                    values.append({
                        "project_id": project_id,
                        "time_created": now,
                        "time_updated": now,
                        "data": json.dumps(data),
                    })
                
                count = cls._insert_batch(
                    session, values, "permission",
                    ["project_id", "time_created", "time_updated", "data"]
                )
                stats.permissions += count
                report_progress("permissions", end - i)
            
            logger.info(f"Migrated {stats.permissions} permissions")
            if orphans["permissions"] > 0:
                logger.warning(f"Skipped {orphans['permissions']} orphaned permissions")
        
        def migrate_shares(session):
            """Migrate session share files."""
            logger.info("Migrating session shares...")
            
            share_sessions = [os.path.basename(f)[:-5] for f in share_files]
            
            for i in range(0, len(share_files), cls.BATCH_SIZE):
                end = min(i + cls.BATCH_SIZE, len(share_files))
                batch = cls._read_json_files(share_files, i, end)
                
                values = []
                for j, data in enumerate(batch):
                    if not data:
                        continue
                    
                    session_id = share_sessions[i + j]
                    
                    if session_id not in session_ids:
                        orphans["shares"] += 1
                        continue
                    
                    if not data.get("id") or not data.get("secret") or not data.get("url"):
                        stats.errors.append(f"Session share missing id/secret/url: {share_files[i + j]}")
                        continue
                    
                    values.append({
                        "session_id": session_id,
                        "id": data["id"],
                        "secret": data["secret"],
                        "url": data["url"],
                        "time_created": now,
                    })
                
                count = cls._insert_batch(
                    session, values, "session_share",
                    ["session_id", "id", "secret", "url", "time_created"]
                )
                stats.shares += count
                report_progress("shares", end - i)
            
            logger.info(f"Migrated {stats.shares} session shares")
            if orphans["shares"] > 0:
                logger.warning(f"Skipped {orphans['shares']} orphaned session shares")
        
        # Run all migrations within a transaction
        def run_all_migrations(session):
            migrate_projects(session)
            migrate_sessions(session)
            migrate_messages(session)
            migrate_parts(session)
            migrate_todos(session)
            migrate_permissions(session)
            migrate_shares(session)
        
        Database.transaction(run_all_migrations)
        
        duration = round((time.time() - start_time) * 1000)  # ms
        
        logger.info(f"JSON migration complete:")
        logger.info(f"  Projects: {stats.projects}")
        logger.info(f"  Sessions: {stats.sessions}")
        logger.info(f"  Messages: {stats.messages}")
        logger.info(f"  Parts: {stats.parts}")
        logger.info(f"  Todos: {stats.todos}")
        logger.info(f"  Permissions: {stats.permissions}")
        logger.info(f"  Shares: {stats.shares}")
        logger.info(f"  Errors: {len(stats.errors)}")
        logger.info(f"  Duration: {duration}ms")
        
        if stats.errors:
            logger.warning(f"Migration errors (first 20): {stats.errors[:20]}")
        
        if progress_callback:
            progress_callback(MigrationProgress(current=total, total=total, label="complete"))
        
        return stats


# Module-level convenience function

def run_json_migration(
    progress_callback: Optional[Callable[[MigrationProgress], None]] = None,
) -> MigrationStats:
    """
    Run JSON to SQLite migration.
    
    Args:
        progress_callback: Optional callback for progress updates
    
    Returns:
        Migration statistics
    """
    return JsonMigration.run(progress_callback)
