"""
Utility module for OpenCode.

Common utilities used across the project.
"""

import asyncio
import hashlib
import os
import re
from pathlib import Path
from typing import Any, Optional, Callable, TypeVar
from functools import wraps


T = TypeVar('T')


def md5_hash(content: str) -> str:
    """Calculate MD5 hash of content."""
    return hashlib.md5(content.encode('utf-8')).hexdigest()


def sha256_hash(content: str) -> str:
    """Calculate SHA256 hash of content."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


async def retry_async(
    func: Callable,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Any:
    """
    Retry an async function with exponential backoff.
    
    Args:
        func: Async function to retry
        max_retries: Maximum number of retries
        delay: Initial delay between retries
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch
    """
    current_delay = delay
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries - 1:
                await asyncio.sleep(current_delay)
                current_delay *= backoff
    
    raise last_exception


def retry_decorator(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """
    Decorator for retrying functions with exponential backoff.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            
            raise last_exception
        
        return wrapper
    return decorator


def truncate_text(text: str, max_length: int = 1000, suffix: str = "...") -> str:
    """Truncate text to a maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def normalize_path(path: str, base_dir: Optional[Path] = None) -> Path:
    """Normalize a path, resolving relative paths against base_dir."""
    p = Path(path)
    if not p.is_absolute() and base_dir:
        p = base_dir / p
    return p.resolve()


def match_glob(path: str, patterns: list[str]) -> bool:
    """
    Check if a path matches any of the given glob patterns.
    
    Args:
        path: Path to check
        patterns: List of glob patterns
    """
    import fnmatch
    
    path_str = str(path)
    for pattern in patterns:
        if fnmatch.fnmatch(path_str, pattern):
            return True
        # Also check just the filename
        if fnmatch.fnmatch(Path(path_str).name, pattern):
            return True
    return False


def is_binary_file(path: Path, sample_size: int = 8192) -> bool:
    """
    Check if a file is likely binary.
    
    Args:
        path: Path to the file
        sample_size: Number of bytes to sample
    """
    try:
        with open(path, 'rb') as f:
            sample = f.read(sample_size)
        
        # Check for null bytes (common in binary files)
        if b'\x00' in sample:
            return True
        
        # Try to decode as text
        try:
            sample.decode('utf-8')
            return False
        except UnicodeDecodeError:
            return True
            
    except (IOError, PermissionError):
        return True


def get_file_encoding(path: Path) -> str:
    """
    Detect file encoding.
    
    Returns 'utf-8' for text files, 'binary' for binary files.
    """
    if is_binary_file(path):
        return 'binary'
    return 'utf-8'


def parse_diff(diff_text: str) -> list[dict]:
    """
    Parse a unified diff into structured format.
    
    Returns a list of hunks with their changes.
    """
    hunks = []
    current_hunk = None
    
    for line in diff_text.split('\n'):
        if line.startswith('@@'):
            # Parse hunk header: @@ -start,count +start,count @@
            match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if match:
                if current_hunk:
                    hunks.append(current_hunk)
                current_hunk = {
                    'old_start': int(match.group(1)),
                    'old_count': int(match.group(2) or 1),
                    'new_start': int(match.group(3)),
                    'new_count': int(match.group(4) or 1),
                    'changes': [],
                }
        elif current_hunk and line.startswith('+') and not line.startswith('+++'):
            current_hunk['changes'].append({
                'type': 'add',
                'content': line[1:],
            })
        elif current_hunk and line.startswith('-') and not line.startswith('---'):
            current_hunk['changes'].append({
                'type': 'remove',
                'content': line[1:],
            })
        elif current_hunk and (line.startswith(' ') or line == ''):
            current_hunk['changes'].append({
                'type': 'context',
                'content': line[1:] if line.startswith(' ') else line,
            })
    
    if current_hunk:
        hunks.append(current_hunk)
    
    return hunks


def run_in_executor(func: Callable, *args, **kwargs) -> Any:
    """Run a synchronous function in an executor."""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, lambda: func(*args, **kwargs))


class AsyncContextManager:
    """Simple async context manager utility."""
    
    def __init__(self, enter: Callable, exit: Callable):
        self._enter = enter
        self._exit = exit
    
    async def __aenter__(self):
        return await self._enter()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._exit(exc_type, exc_val, exc_tb)


def debounce(wait_seconds: float):
    """
    Decorator to debounce a function call.
    
    Only the last call within the wait period will be executed.
    """
    def decorator(func: Callable) -> Callable:
        task = None
        
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            nonlocal task
            if task:
                task.cancel()
            
            async def delayed_call():
                await asyncio.sleep(wait_seconds)
                return await func(*args, **kwargs)
            
            task = asyncio.create_task(delayed_call())
            return await task
        
        return wrapper
    return decorator


def throttle(interval_seconds: float):
    """
    Decorator to throttle a function call.
    
    Ensures at least interval_seconds between calls.
    """
    def decorator(func: Callable) -> Callable:
        last_call = 0.0
        lock = asyncio.Lock()
        
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            nonlocal last_call
            
            async with lock:
                now = asyncio.get_event_loop().time()
                elapsed = now - last_call
                
                if elapsed < interval_seconds:
                    await asyncio.sleep(interval_seconds - elapsed)
                
                last_call = asyncio.get_event_loop().time()
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def format_bytes(size: int) -> str:
    """Format bytes into human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def format_duration(seconds: float) -> str:
    """Format duration into human-readable string."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


def slugify(text: Optional[str] = None) -> str:
    """
    Convert text to a URL-friendly slug.
    
    Args:
        text: Text to slugify. If None, generates a random slug.
    
    Returns:
        Slugified string
    """
    import re
    import uuid
    
    if text is None:
        return str(uuid.uuid4())[:8]
    
    # Convert to lowercase
    slug = text.lower()
    
    # Remove non-word characters (except hyphens and spaces)
    slug = re.sub(r'[^\w\s-]', '', slug)
    
    # Replace spaces with hyphens
    slug = re.sub(r'[\s_]+', '-', slug)
    
    # Remove multiple consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    
    # Strip leading/trailing hyphens
    slug = slug.strip('-')
    
    return slug or str(uuid.uuid4())[:8]


def defer(fn: Callable):
    """
    Create a context manager that defers execution of a function.
    
    This is used for cleanup operations that should run at the end of a scope.
    
    Args:
        fn: Function to defer execution
    
    Returns:
        A simple context manager object
    """
    class DeferContext:
        def __enter__(self):
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            fn()
    
    return DeferContext()
