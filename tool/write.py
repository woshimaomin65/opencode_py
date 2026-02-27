"""
Write tool for OpenCode.

Writes content to files with:
- Directory creation
- Diff generation
- LSP integration
"""

import os
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass
from difflib import unified_diff

from tool.tool import BaseTool, ToolDefinition, ToolParameter, ToolResult, ToolStatus, ToolContext


@dataclass
class WriteToolConfig:
    """Configuration for WriteTool."""
    working_dir: Optional[Path] = None


class WriteTool(BaseTool):
    """Tool for writing files."""
    
    def __init__(self, config: Optional[WriteToolConfig] = None):
        self.config = config or WriteToolConfig()
        self.working_dir = self.config.working_dir or Path.cwd()
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="write",
            description="Write content to a file (creates or overwrites)",
            parameters=[
                ToolParameter(
                    name="filePath",
                    type="string",
                    description="The absolute path to the file to write (must be absolute, not relative)",
                    required=True,
                ),
                ToolParameter(
                    name="content",
                    type="string",
                    description="The content to write to the file",
                    required=True,
                ),
            ],
        )
    
    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        file_path = kwargs.get("filePath")
        content = kwargs.get("content")
        
        if not file_path:
            return ToolResult(
                tool_name="write",
                status=ToolStatus.ERROR,
                content=None,
                error="Missing required parameter: filePath",
            )
        
        if content is None:
            return ToolResult(
                tool_name="write",
                status=ToolStatus.ERROR,
                content=None,
                error="Missing required parameter: content",
            )
        
        try:
            # Resolve path
            path = Path(file_path)
            if not path.is_absolute():
                path = self.working_dir / path
            
            # Check if file exists
            exists = path.exists()
            content_old = ""
            if exists:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    content_old = f.read()
            
            # Generate diff
            diff = self._generate_diff(str(path), content_old, content)
            
            # Request permission
            rel_path = str(path.relative_to(self.working_dir)) if path.is_relative_to(self.working_dir) else str(path)
            await ctx.ask(
                permission="edit",
                patterns=[rel_path],
                always=["*"],
                metadata={
                    "filePath": str(path),
                    "diff": diff,
                },
            )
            
            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Build output
            output = "Wrote file successfully."
            
            # Note: LSP integration would go here
            # diagnostics = await LSP.diagnostics()
            # ... process diagnostics ...
            
            return ToolResult(
                tool_name="write",
                status=ToolStatus.SUCCESS,
                content=output,
                title=rel_path,
                metadata={
                    "diagnostics": {},
                    "filePath": str(path),
                    "exists": exists,
                },
            )
            
        except Exception as e:
            return ToolResult(
                tool_name="write",
                status=ToolStatus.ERROR,
                content=None,
                error=str(e),
            )
    
    def _generate_diff(self, filepath: str, old_content: str, new_content: str) -> str:
        """Generate a unified diff between old and new content."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        diff_lines = list(unified_diff(
            old_lines,
            new_lines,
            fromfile=filepath,
            tofile=filepath,
            n=3,
        ))
        
        # Trim diff header lines
        trimmed_lines = []
        for line in diff_lines:
            if line.startswith("---") or line.startswith("+++"):
                continue
            trimmed_lines.append(line)
        
        return "".join(trimmed_lines) if trimmed_lines else ""
