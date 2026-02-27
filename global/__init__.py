"""
Global path utilities for OpenCode.

Provides access to application-wide paths:
- Data directory
- Config directory
- Cache directory
- Storage directory
"""

import os
from pathlib import Path
from typing import Optional


# Global path state
_data_path: Optional[str] = None
_config_path: Optional[str] = None
_cache_path: Optional[str] = None


def get_data_path() -> str:
    """
    Get the data directory path.
    
    Returns:
        Path to the data directory
    """
    global _data_path
    if _data_path is None:
        # Check environment variable first
        _data_path = os.environ.get("OPENCODE_DATA_DIR")
        
        if not _data_path:
            # Use platform-specific default
            if os.name == "nt":  # Windows
                appdata = os.environ.get("APPDATA", "")
                _data_path = os.path.join(appdata, "opencode")
            else:  # Unix-like
                xdg_data = os.environ.get("XDG_DATA_HOME", "")
                if xdg_data:
                    _data_path = os.path.join(xdg_data, "opencode")
                else:
                    home = os.path.expanduser("~")
                    _data_path = os.path.join(home, ".local", "share", "opencode")
        
        # Create directory if it doesn't exist
        os.makedirs(_data_path, exist_ok=True)
    
    return _data_path


def get_config_path() -> str:
    """
    Get the config directory path.
    
    Returns:
        Path to the config directory
    """
    global _config_path
    if _config_path is None:
        # Check environment variable first
        _config_path = os.environ.get("OPENCODE_CONFIG_DIR")
        
        if not _config_path:
            # Use platform-specific default
            if os.name == "nt":  # Windows
                appdata = os.environ.get("APPDATA", "")
                _config_path = os.path.join(appdata, "opencode", "config")
            else:  # Unix-like
                xdg_config = os.environ.get("XDG_CONFIG_HOME", "")
                if xdg_config:
                    _config_path = os.path.join(xdg_config, "opencode")
                else:
                    home = os.path.expanduser("~")
                    _config_path = os.path.join(home, ".config", "opencode")
        
        # Create directory if it doesn't exist
        os.makedirs(_config_path, exist_ok=True)
    
    return _config_path


def get_cache_path() -> str:
    """
    Get the cache directory path.
    
    Returns:
        Path to the cache directory
    """
    global _cache_path
    if _cache_path is None:
        # Check environment variable first
        _cache_path = os.environ.get("OPENCODE_CACHE_DIR")
        
        if not _cache_path:
            # Use platform-specific default
            if os.name == "nt":  # Windows
                localappdata = os.environ.get("LOCALAPPDATA", "")
                _cache_path = os.path.join(localappdata, "opencode", "cache")
            else:  # Unix-like
                xdg_cache = os.environ.get("XDG_CACHE_HOME", "")
                if xdg_cache:
                    _cache_path = os.path.join(xdg_cache, "opencode")
                else:
                    home = os.path.expanduser("~")
                    _cache_path = os.path.join(home, ".cache", "opencode")
        
        # Create directory if it doesn't exist
        os.makedirs(_cache_path, exist_ok=True)
    
    return _cache_path


def set_data_path(path: str) -> None:
    """
    Set a custom data directory path.
    
    Args:
        path: Custom data directory path
    """
    global _data_path
    _data_path = path
    os.makedirs(_data_path, exist_ok=True)


def set_config_path(path: str) -> None:
    """
    Set a custom config directory path.
    
    Args:
        path: Custom config directory path
    """
    global _config_path
    _config_path = path
    os.makedirs(_config_path, exist_ok=True)


def set_cache_path(path: str) -> None:
    """
    Set a custom cache directory path.
    
    Args:
        path: Custom cache directory path
    """
    global _cache_path
    _cache_path = path
    os.makedirs(_cache_path, exist_ok=True)
