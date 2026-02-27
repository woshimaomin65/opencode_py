"""
Read tool for OpenCode.

Reads file contents with support for:
- Line limits and offsets
- Directory listing
- Binary file detection
- Image/PDF handling
"""

import os
import mimetypes
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass

from .tool import BaseTool, ToolDefinition, ToolParameter, ToolResult, ToolStatus, ToolContext


# Configuration constants
DEFAULT_READ_LIMIT = 2000
MAX_LINE_LENGTH = 2000
MAX_BYTES = 50 * 1024  # 50KB

# Binary file extensions
BINARY_EXTENSIONS = {
    '.zip', '.tar', '.gz', '.exe', '.dll', '.so', '.class', '.jar', '.war',
    '.7z', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods',
    '.odp', '.bin', '.dat', '.obj', '.o', '.a', '.lib', '.wasm', '.pyc', '.pyo',
}


@dataclass
class ReadToolConfig:
    """Configuration for ReadTool."""
    working_dir: Optional[Path] = None
    default_limit: int = DEFAULT_READ_LIMIT
    max_line_length: int = MAX_LINE_LENGTH
    max_bytes: int = MAX_BYTES


class ReadTool(BaseTool):
    """Tool for reading files."""
    
    def __init__(self, config: Optional[ReadToolConfig] = None):
        self.config = config or ReadToolConfig()
        self.working_dir = self.config.working_dir or Path.cwd()
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="read",
            description="Read the contents of a file or directory",
            parameters=[
                ToolParameter(
                    name="filePath",
                    type="string",
                    description="The absolute path to the file or directory to read",
                    required=True,
                ),
                ToolParameter(
                    name="offset",
                    type="number",
                    description="The line number to start reading from (1-indexed)",
                    required=False,
                ),
                ToolParameter(
                    name="limit",
                    type="number",
                    description=f"The maximum number of lines to read (defaults to {DEFAULT_READ_LIMIT})",
                    required=False,
                ),
            ],
        )
    
    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        file_path = kwargs.get("filePath")
        offset = kwargs.get("offset")
        limit = kwargs.get("limit", self.config.default_limit)
        
        if not file_path:
            return ToolResult(
                tool_name="read",
                status=ToolStatus.ERROR,
                content=None,
                error="Missing required parameter: filePath",
            )
        
        try:
            # Resolve path
            path = Path(file_path)
            if not path.is_absolute():
                path = self.working_dir / path
            
            # Validate offset
            if offset is not None and offset < 1:
                return ToolResult(
                    tool_name="read",
                    status=ToolStatus.ERROR,
                    content=None,
                    error="offset must be greater than or equal to 1",
                )
            
            # Request permission
            await ctx.ask(
                permission="read",
                patterns=[str(path)],
                always=["*"],
                metadata={"filePath": str(path)},
            )
            
            # Check if path exists
            if not path.exists():
                # Try to suggest similar files
                suggestions = self._find_similar_files(path)
                if suggestions:
                    suggestion_list = "\n".join(suggestions[:3])
                    return ToolResult(
                        tool_name="read",
                        status=ToolStatus.ERROR,
                        content=None,
                        error=f"File not found: {path}\n\nDid you mean one of these?\n{suggestion_list}",
                    )
                return ToolResult(
                    tool_name="read",
                    status=ToolStatus.ERROR,
                    content=None,
                    error=f"File not found: {path}",
                )
            
            # Handle directory
            if path.is_dir():
                return await self._read_directory(ctx, path, offset, limit)
            
            # Handle file
            return await self._read_file(ctx, path, offset, limit)
            
        except Exception as e:
            return ToolResult(
                tool_name="read",
                status=ToolStatus.ERROR,
                content=None,
                error=str(e),
            )
    
    def _find_similar_files(self, path: Path) -> list[str]:
        """Find files with similar names."""
        if not path.parent.exists():
            return []
        
        base = path.name.lower()
        suggestions = []
        
        try:
            for entry in path.parent.iterdir():
                entry_name = entry.name.lower()
                if base in entry_name or entry_name in base:
                    suggestions.append(str(entry))
        except (PermissionError, OSError):
            pass
        
        return suggestions
    
    async def _read_directory(self, ctx: ToolContext, path: Path, offset: Optional[int], limit: int) -> ToolResult:
        """Read a directory listing."""
        try:
            entries = []
            for entry in path.iterdir():
                if entry.is_dir():
                    entries.append(entry.name + "/")
                elif entry.is_symlink():
                    try:
                        if entry.resolve().is_dir():
                            entries.append(entry.name + "/")
                        else:
                            entries.append(entry.name)
                    except (OSError, PermissionError):
                        entries.append(entry.name)
                else:
                    entries.append(entry.name)
            
            entries.sort()
            
            # Apply offset and limit
            start = (offset - 1) if offset else 0
            sliced = entries[start:start + limit]
            truncated = start + len(sliced) < len(entries)
            
            output_lines = [
                f"<path>{path}</path>",
                "<type>directory</type>",
                "<entries>",
                "\n".join(sliced),
            ]
            
            if truncated:
                output_lines.append(f"\n(Showing {len(sliced)} of {len(entries)} entries. Use 'offset' parameter to read beyond entry {start + len(sliced)})")
            else:
                output_lines.append(f"\n({len(entries)} entries)")
            
            output_lines.append("</entries>")
            output = "\n".join(output_lines)
            
            return ToolResult(
                tool_name="read",
                status=ToolStatus.SUCCESS,
                content=output,
                title=str(path.relative_to(self.working_dir)) if path.is_relative_to(self.working_dir) else str(path),
                metadata={
                    "preview": "\n".join(sliced[:20]),
                    "truncated": truncated,
                    "loaded": [],
                },
            )
            
        except Exception as e:
            return ToolResult(
                tool_name="read",
                status=ToolStatus.ERROR,
                content=None,
                error=str(e),
            )
    
    async def _read_file(self, ctx: ToolContext, path: Path, offset: Optional[int], limit: int) -> ToolResult:
        """Read a file's contents."""
        try:
            # Check file type
            mime_type, _ = mimetypes.guess_type(path)
            
            # Handle images and PDFs
            is_image = mime_type and mime_type.startswith("image/") and mime_type not in ["image/svg+xml", "image/vnd.fastbidsheet"]
            is_pdf = mime_type == "application/pdf"
            
            if is_image or is_pdf:
                with open(path, "rb") as f:
                    content = f.read()
                
                import base64
                base64_content = base64.b64encode(content).decode('utf-8')
                msg = "Image read successfully" if is_image else "PDF read successfully"
                
                return ToolResult(
                    tool_name="read",
                    status=ToolStatus.SUCCESS,
                    content=msg,
                    title=str(path.relative_to(self.working_dir)) if path.is_relative_to(self.working_dir) else str(path),
                    metadata={
                        "preview": msg,
                        "truncated": False,
                        "loaded": [],
                    },
                    attachments=[{
                        "type": "file",
                        "mime": mime_type,
                        "url": f"data:{mime_type};base64,{base64_content}",
                    }],
                )
            
            # Check for binary file
            if self._is_binary_file(path):
                return ToolResult(
                    tool_name="read",
                    status=ToolStatus.ERROR,
                    content=None,
                    error=f"Cannot read binary file: {path}",
                )
            
            # Read text file
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            start = (offset - 1) if offset else 0
            
            if start >= total_lines:
                return ToolResult(
                    tool_name="read",
                    status=ToolStatus.ERROR,
                    content=None,
                    error=f"Offset {offset} is out of range for this file ({total_lines} lines)",
                )
            
            # Read lines with limits
            raw_lines = []
            bytes_count = 0
            truncated_by_bytes = False
            
            end = min(total_lines, start + limit)
            for i in range(start, end):
                line = lines[i]
                if len(line) > self.config.max_line_length:
                    line = line[:self.config.max_line_length] + "..."
                
                size = len(line.encode('utf-8')) + (1 if raw_lines else 0)
                if bytes_count + size > self.config.max_bytes:
                    truncated_by_bytes = True
                    break
                
                raw_lines.append(line.rstrip('\n'))
                bytes_count += size
            
            # Format output with line numbers
            content_lines = []
            for i, line in enumerate(raw_lines):
                content_lines.append(f"{i + offset if offset else i + 1}: {line}")
            
            output_lines = [
                f"<path>{path}</path>",
                "<type>file</type>",
                "<content>",
                "\n".join(content_lines),
            ]
            
            last_read_line = (offset if offset else 1) + len(raw_lines) - 1
            has_more_lines = total_lines > last_read_line
            truncated = has_more_lines or truncated_by_bytes
            
            if truncated_by_bytes:
                output_lines.append(f"\n\n(Output truncated at {self.config.max_bytes} bytes. Use 'offset' parameter to read beyond line {last_read_line})")
            elif has_more_lines:
                output_lines.append(f"\n\n(File has more lines. Use 'offset' parameter to read beyond line {last_read_line})")
            else:
                output_lines.append(f"\n\n(End of file - total {total_lines} lines)")
            
            output_lines.append("</content>")
            output = "\n".join(output_lines)
            
            return ToolResult(
                tool_name="read",
                status=ToolStatus.SUCCESS,
                content=output,
                title=str(path.relative_to(self.working_dir)) if path.is_relative_to(self.working_dir) else str(path),
                metadata={
                    "preview": "\n".join(raw_lines[:20]),
                    "truncated": truncated,
                    "loaded": [],
                },
            )
            
        except UnicodeDecodeError as e:
            return ToolResult(
                tool_name="read",
                status=ToolStatus.ERROR,
                content=None,
                error=f"Cannot decode file as text: {e}",
            )
        except Exception as e:
            return ToolResult(
                tool_name="read",
                status=ToolStatus.ERROR,
                content=None,
                error=str(e),
            )
    
    def _is_binary_file(self, path: Path) -> bool:
        """Check if a file is binary."""
        # Check extension first
        if path.suffix.lower() in BINARY_EXTENSIONS:
            return True
        
        try:
            # Check file size
            file_size = path.stat().st_size
            if file_size == 0:
                return False
            
            # Read first 4KB and check for binary content
            buffer_size = min(4096, file_size)
            with open(path, 'rb') as f:
                buffer = f.read(buffer_size)
            
            if len(buffer) == 0:
                return False
            
            # Check for null bytes and non-printable characters
            non_printable_count = 0
            for byte in buffer:
                if byte == 0:
                    return True
                if byte < 9 or (byte > 13 and byte < 32):
                    non_printable_count += 1
            
            # If >30% non-printable characters, consider it binary
            return non_printable_count / len(buffer) > 0.3
            
        except (OSError, PermissionError):
            return False
