"""
Store module for OpenCode.

Provides storage management functionality:
- Storage directory management and migrations
- Database operations via SQLAlchemy
- JSON file storage with locking
- JSON to SQLite migration utilities
"""

from opencode.store.storage import (
    Storage,
    StorageNotFoundError,
    read,
    write,
    update,
    remove,
    list_files,
    initialize_storage,
)

from opencode.store.db import (
    Database,
    DatabaseNotFoundError,
    get_database,
    use_database,
    transaction,
    effect,
)

from opencode.store.schema import (
    Base,
    TimestampMixin,
)

from opencode.store.migration import (
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
