"""
Format module for OpenCode.

Handles formatting of various outputs including:
- Code formatting
- Message formatting
- Table formatting
- Time formatting
"""

import re
from datetime import datetime
from typing import Any, Optional, Union


def format_duration(seconds: float, precise: bool = False) -> str:
    """
    Format a duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        precise: Whether to show precise breakdown
        
    Returns:
        Formatted duration string
    """
    if seconds < 0:
        return "0s"
    
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    
    if seconds < 60:
        if precise:
            return f"{seconds:.2f}s"
        return f"{int(seconds)}s"
    
    if seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        if precise:
            return f"{minutes}m {secs}s"
        return f"{minutes}m"
    
    if seconds < 86400:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        if precise:
            secs = int(seconds % 60)
            return f"{hours}h {minutes}m {secs}s"
        return f"{hours}h {minutes}m"
    
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    if precise:
        minutes = int((seconds % 3600) // 60)
        return f"{days}d {hours}h {minutes}m"
    return f"{days}d"


def format_bytes(size: Union[int, float], precision: int = 2) -> str:
    """
    Format bytes to human-readable string.
    
    Args:
        size: Size in bytes
        precision: Decimal precision
        
    Returns:
        Formatted size string
    """
    if size < 0:
        return "0B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit_index = 0
    size_float = float(size)
    
    while size_float >= 1024 and unit_index < len(units) - 1:
        size_float /= 1024
        unit_index += 1
    
    if unit_index == 0:
        return f"{int(size_float)}B"
    
    return f"{size_float:.{precision}f} {units[unit_index]}"


def format_datetime(dt: datetime, format_type: str = "iso") -> str:
    """
    Format a datetime object.
    
    Args:
        dt: Datetime object
        format_type: Format type ('iso', 'human', 'relative')
        
    Returns:
        Formatted datetime string
    """
    if format_type == "iso":
        return dt.isoformat()
    
    if format_type == "human":
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    
    if format_type == "date":
        return dt.strftime("%Y-%m-%d")
    
    if format_type == "time":
        return dt.strftime("%H:%M:%S")
    
    if format_type == "relative":
        return format_relative_time(dt)
    
    return dt.isoformat()


def format_relative_time(dt: datetime) -> str:
    """
    Format datetime as relative time (e.g., '5 minutes ago').
    
    Args:
        dt: Datetime object
        
    Returns:
        Relative time string
    """
    now = datetime.now()
    diff = now - dt
    seconds = diff.total_seconds()
    
    if seconds < 0:
        return "in the future"
    
    if seconds < 60:
        return "just now"
    
    if seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    
    if seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    
    if seconds < 604800:
        days = int(seconds // 86400)
        return f"{days} day{'s' if days > 1 else ''} ago"
    
    if seconds < 2592000:
        weeks = int(seconds // 604800)
        return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    
    if seconds < 31536000:
        months = int(seconds // 2592000)
        return f"{months} month{'s' if months > 1 else ''} ago"
    
    years = int(seconds // 31536000)
    return f"{years} year{'s' if years > 1 else ''} ago"


def format_table(rows: list[list[str]], headers: Optional[list[str]] = None) -> str:
    """
    Format data as a text table.
    
    Args:
        rows: List of rows (each row is a list of cell values)
        headers: Optional header row
        
    Returns:
        Formatted table string
    """
    if not rows:
        return ""
    
    # Include headers in column width calculation
    all_rows = [headers] + rows if headers else rows
    
    # Calculate column widths
    num_cols = max(len(row) for row in all_rows)
    col_widths = [0] * num_cols
    
    for row in all_rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    
    # Format rows
    lines = []
    
    def format_row(row: list[str]) -> str:
        padded_cells = []
        for i, cell in enumerate(row):
            cell_str = str(cell)
            padded_cells.append(cell_str.ljust(col_widths[i]))
        return " | ".join(padded_cells)
    
    if headers:
        lines.append(format_row(headers))
        lines.append("-+-".join("-" * w for w in col_widths))
    
    for row in rows:
        lines.append(format_row(row))
    
    return "\n".join(lines)


def format_code_block(code: str, language: Optional[str] = None) -> str:
    """
    Format code as a markdown code block.
    
    Args:
        code: Code content
        language: Optional language identifier
        
    Returns:
        Formatted code block
    """
    if language:
        return f"```{language}\n{code}\n```"
    return f"```\n{code}\n```"


def format_truncate(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_number(num: Union[int, float], separator: str = ",") -> str:
    """
    Format a number with thousand separators.
    
    Args:
        num: Number to format
        separator: Thousand separator character
        
    Returns:
        Formatted number string
    """
    if isinstance(num, float):
        int_part = int(num)
        dec_part = num - int_part
        if dec_part == 0:
            return f"{int_part:,}".replace(",", separator)
        return f"{num:,.2f}".replace(",", separator)
    return f"{num:,}".replace(",", separator)


def format_list(items: list[Any], separator: str = ", ", last_separator: str = " and ") -> str:
    """
    Format a list as a natural language string.
    
    Args:
        items: List of items
        separator: Separator between items
        last_separator: Separator before last item
        
    Returns:
        Formatted list string
    """
    if not items:
        return ""
    
    if len(items) == 1:
        return str(items[0])
    
    if len(items) == 2:
        return f"{items[0]}{last_separator}{items[1]}"
    
    return separator.join(str(item) for item in items[:-1]) + f"{last_separator}{items[-1]}"


def format_path(path: str, max_length: int = 50) -> str:
    """
    Format a file path, truncating if necessary.
    
    Args:
        path: File path
        max_length: Maximum length
        
    Returns:
        Formatted path
    """
    if len(path) <= max_length:
        return path
    
    # Try to show beginning and end
    parts = path.split("/")
    if len(parts) > 2:
        # Show first and last parts
        result = "/".join(parts[:2]) + "/.../" + parts[-1]
        if len(result) <= max_length:
            return result
    
    # Fall back to simple truncation
    return "..." + path[-(max_length - 3):]


def indent_text(text: str, spaces: int = 4) -> str:
    """
    Add indentation to each line of text.
    
    Args:
        text: Text to indent
        spaces: Number of spaces per indent level
        
    Returns:
        Indented text
    """
    indent = " " * spaces
    lines = text.split("\n")
    return "\n".join(indent + line for line in lines)


def strip_ansi(text: str) -> str:
    """
    Remove ANSI escape codes from text.
    
    Args:
        text: Text with potential ANSI codes
        
    Returns:
        Text without ANSI codes
    """
    ansi_pattern = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
    return ansi_pattern.sub('', text)


def wrap_text(text: str, width: int = 80) -> str:
    """
    Wrap text to specified width.
    
    Args:
        text: Text to wrap
        width: Maximum line width
        
    Returns:
        Wrapped text
    """
    words = text.split()
    if not words:
        return ""
    
    lines = []
    current_line = words[0]
    
    for word in words[1:]:
        if len(current_line) + 1 + len(word) <= width:
            current_line += " " + word
        else:
            lines.append(current_line)
            current_line = word
    
    if current_line:
        lines.append(current_line)
    
    return "\n".join(lines)
