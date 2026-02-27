"""
Database module for OpenCode Store.

Provides database operations using SQLAlchemy with SQLite.
- Database connection management
- Transaction support
- Migration execution
- Context-aware database access
"""

import os
import logging
from pathlib import Path
from typing import Any, Callable, TypeVar, Optional, List
from contextvars import ContextVar
from functools import wraps

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session as DBSession, scoped_session
from sqlalchemy.engine import Engine

from .schema import Base

logger = logging.getLogger(__name__)


T = TypeVar('T')


class DatabaseNotFoundError(Exception):
    """Raised when a database resource is not found."""
    
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


# Context variable for transaction-aware database access
_db_context: ContextVar[Optional[dict]] = ContextVar('db_context', default=None)


class Database:
    """
    Database manager for SQLite operations.
    
    Provides:
    - Connection management with optimized SQLite settings
    - Transaction support with context awareness
    - Migration execution
    - Effect registration for post-commit actions
    """
    
    _engine: Optional[Engine] = None
    _session_factory: Optional[scoped_session] = None
    _path: Optional[str] = None
    
    @classmethod
    def initialize(cls, db_path: Optional[str] = None) -> None:
        """
        Initialize the database connection.
        
        Args:
            db_path: Path to the SQLite database file. If None, uses default location.
        """
        if db_path is None:
            from .global_path import get_data_path
            db_path = os.path.join(get_data_path(), "opencode.db")
        
        cls._path = db_path
        db_dir = os.path.dirname(db_path)
        
        # Create directory if it doesn't exist
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        logger.info(f"Opening database: {db_path}")
        
        # Create engine with SQLite optimizations
        cls._engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            connect_args={
                "check_same_thread": False,  # Required for threading
            },
        )
        
        # Apply SQLite optimizations via event listener
        from sqlalchemy import event
        
        @event.listens_for(cls._engine, "connect")
        def set_sqlite_pragmas(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA synchronous = NORMAL")
            cursor.execute("PRAGMA busy_timeout = 5000")
            cursor.execute("PRAGMA cache_size = -64000")  # 64MB cache
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("PRAGMA wal_checkpoint(PASSIVE)")
            cursor.close()
        
        # Create session factory
        cls._session_factory = scoped_session(sessionmaker(bind=cls._engine))
        
        # Create all tables
        Base.metadata.create_all(cls._engine)
        
        logger.info("Database initialized successfully")
    
    @classmethod
    def get_path(cls) -> str:
        """Get the database path."""
        if cls._path is None:
            from .global_path import get_data_path
            cls._path = os.path.join(get_data_path(), "opencode.db")
        return cls._path
    
    @classmethod
    def get_engine(cls) -> Engine:
        """Get the database engine."""
        if cls._engine is None:
            cls.initialize()
        return cls._engine
    
    @classmethod
    def get_session(cls) -> DBSession:
        """Get a database session."""
        if cls._session_factory is None:
            cls.initialize()
        return cls._session_factory()
    
    @classmethod
    def close(cls) -> None:
        """Close the database connection."""
        if cls._session_factory:
            cls._session_factory.remove()
        if cls._engine:
            cls._engine.dispose()
            cls._engine = None
        cls._session_factory = None
    
    @classmethod
    def use(cls, callback: Callable[[DBSession], T]) -> T:
        """
        Execute a function with a database session.
        
        If called within a transaction context, uses the existing transaction.
        Otherwise, creates a new session and commits automatically.
        
        Args:
            callback: Function that takes a session and returns a value
        
        Returns:
            The return value of the callback
        """
        context = _db_context.get()
        
        if context is not None:
            # We're in a transaction context
            return callback(context['tx'])
        else:
            # No active transaction, create a new session
            session = cls.get_session()
            effects: List[Callable] = []
            
            try:
                # Provide context for nested calls
                token = _db_context.set({'tx': session, 'effects': effects})
                try:
                    result = callback(session)
                    session.commit()
                    
                    # Execute effects after commit
                    for effect_fn in effects:
                        effect_fn()
                    
                    return result
                finally:
                    _db_context.reset(token)
            except Exception as e:
                session.rollback()
                raise e
            finally:
                session.close()
    
    @classmethod
    def transaction(cls, callback: Callable[[DBSession], T]) -> T:
        """
        Execute a function within a database transaction.
        
        Provides transaction isolation and atomicity.
        Effects registered within the transaction are executed after commit.
        
        Args:
            callback: Function that takes a session and returns a value
        
        Returns:
            The return value of the callback
        """
        context = _db_context.get()
        
        if context is not None:
            # Already in a transaction, just call the callback
            return callback(context['tx'])
        else:
            # Start a new transaction
            session = cls.get_session()
            effects: List[Callable] = []
            
            try:
                token = _db_context.set({'tx': session, 'effects': effects})
                try:
                    result = callback(session)
                    session.commit()
                    
                    # Execute effects after commit
                    for effect_fn in effects:
                        effect_fn()
                    
                    return result
                finally:
                    _db_context.reset(token)
            except Exception as e:
                session.rollback()
                raise e
            finally:
                session.close()
    
    @classmethod
    def effect(cls, func: Callable[[], Any]) -> None:
        """
        Register an effect to be executed after the current transaction commits.
        
        Effects are useful for side effects like publishing events that should
        only happen if the transaction succeeds.
        
        Args:
            func: Function to execute after commit
        """
        context = _db_context.get()
        
        if context is not None:
            context['effects'].append(func)
        else:
            # No active transaction, execute immediately
            func()
    
    @classmethod
    def execute_sql(cls, sql: str, params: Optional[dict] = None) -> Any:
        """
        Execute raw SQL.
        
        Args:
            sql: SQL statement
            params: Optional parameters
        
        Returns:
            Query result
        """
        def _execute(session: DBSession):
            result = session.execute(text(sql), params or {})
            return result
        
        return cls.use(_execute)


# Module-level convenience functions

_database_instance: Optional[Database] = None


def get_database() -> Database:
    """Get the database instance."""
    global _database_instance
    if _database_instance is None:
        _database_instance = Database()
    return _database_instance


def use_database(callback: Callable[[DBSession], T]) -> T:
    """Execute a function with database access."""
    return Database.use(callback)


def transaction(callback: Callable[[DBSession], T]) -> T:
    """Execute a function within a transaction."""
    return Database.transaction(callback)


def effect(func: Callable[[], Any]) -> None:
    """Register an effect for post-commit execution."""
    Database.effect(func)
