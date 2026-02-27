"""
Store module for OpenCode.

Provides storage management functionality:
- Storage directory management and migrations
- Database operations via SQLAlchemy
- JSON file storage with locking
- JSON to SQLite migration utilities
"""

from .storage import (
    Storage,
    StorageNotFoundError,
    read,
    write,
    update,
    remove,
    list_files,
    initialize_storage,
)

from .db import (
    Database,
    DatabaseNotFoundError,
    get_database,
    use_database,
    transaction,
    effect,
)

from .schema import (
    Base,
    TimestampMixin,
)

from .migration import (
    JsonMigration,
    MigrationProgress,
    run_json_migration,
)


__all__ = [
    # Storage
    "Storage",
    "StorageNotFoundError",
    "read",
    "write",
    "update",
    "remove",
    "list_files",
    "initialize_storage",
    # Database
    "Database",
    "DatabaseNotFoundError",
    "get_database",
    "use_database",
    "transaction",
    "effect",
    # Schema
    "Base",
    "TimestampMixin",
    # Migration
    "JsonMigration",
    "MigrationProgress",
    "run_json_migration",
]
