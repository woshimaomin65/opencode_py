"""
Database schema definitions for OpenCode Store module.

Defines base classes and common schema elements used across the application.
"""

from datetime import datetime
from sqlalchemy import Column, Integer
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class TimestampMixin:
    """Mixin class that adds timestamp columns to models."""
    
    time_created = Column(Integer, nullable=False, default=lambda: int(datetime.now().timestamp() * 1000))
    time_updated = Column(Integer, nullable=False, default=lambda: int(datetime.now().timestamp() * 1000), onupdate=lambda: int(datetime.now().timestamp() * 1000))
