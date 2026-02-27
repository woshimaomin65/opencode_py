"""
ID module for OpenCode.

Handles unique ID generation for sessions, messages, tools, etc.
"""

import uuid
import hashlib
import time
from typing import Optional


def generate_id(prefix: str = "") -> str:
    """
    Generate a unique ID.
    
    Args:
        prefix: Optional prefix for the ID
        
    Returns:
        A unique ID string with optional prefix
    """
    unique_id = str(uuid.uuid4())
    if prefix:
        return f"{prefix}_{unique_id}"
    return unique_id


def generate_short_id(prefix: str = "", length: int = 8) -> str:
    """
    Generate a short unique ID.
    
    Args:
        prefix: Optional prefix for the ID
        length: Length of the ID portion (default: 8)
        
    Returns:
        A short unique ID string
    """
    unique_id = uuid.uuid4().hex[:length]
    if prefix:
        return f"{prefix}_{unique_id}"
    return unique_id


def generate_deterministic_id(seed: str, prefix: str = "") -> str:
    """
    Generate a deterministic ID from a seed string.
    
    Args:
        seed: Seed string for ID generation
        prefix: Optional prefix for the ID
        
    Returns:
        A deterministic ID string
    """
    hash_obj = hashlib.sha256(seed.encode('utf-8'))
    unique_id = hash_obj.hexdigest()[:16]
    if prefix:
        return f"{prefix}_{unique_id}"
    return unique_id


def generate_timestamp_id(prefix: str = "") -> str:
    """
    Generate a time-based ID.
    
    Args:
        prefix: Optional prefix for the ID
        
    Returns:
        A time-based ID string
    """
    timestamp = int(time.time() * 1000)  # milliseconds
    unique_part = uuid.uuid4().hex[:8]
    id_str = f"{timestamp}_{unique_part}"
    if prefix:
        return f"{prefix}_{id_str}"
    return id_str


class IDGenerator:
    """
    Stateful ID generator with counter support.
    """
    
    def __init__(self, prefix: str = ""):
        self.prefix = prefix
        self._counter = 0
    
    def generate(self) -> str:
        """Generate an ID with incrementing counter."""
        self._counter += 1
        unique_id = uuid.uuid4().hex[:8]
        if self.prefix:
            return f"{self.prefix}_{self._counter}_{unique_id}"
        return f"{self._counter}_{unique_id}"
    
    def generate_short(self) -> str:
        """Generate a short ID without counter."""
        unique_id = uuid.uuid4().hex[:8]
        if self.prefix:
            return f"{self.prefix}_{unique_id}"
        return unique_id
    
    def reset(self) -> None:
        """Reset the counter."""
        self._counter = 0
    
    @property
    def counter(self) -> int:
        """Get current counter value."""
        return self._counter


# Global ID generators for different entity types
_session_id_generator = IDGenerator("session")
_message_id_generator = IDGenerator("message")
_tool_call_id_generator = IDGenerator("tool")
_request_id_generator = IDGenerator("req")
_part_id_generator = IDGenerator("part")


def generate_session_id() -> str:
    """Generate a session ID."""
    return _session_id_generator.generate()


def generate_message_id() -> str:
    """Generate a message ID."""
    return _message_id_generator.generate()


def generate_tool_call_id() -> str:
    """Generate a tool call ID."""
    return _tool_call_id_generator.generate()


def generate_request_id() -> str:
    """Generate a request ID."""
    return _request_id_generator.generate()


def generate_part_id() -> str:
    """Generate a part ID."""
    return _part_id_generator.generate()
