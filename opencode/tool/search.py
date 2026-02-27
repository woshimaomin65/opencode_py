"""
Search tool for OpenCode.

Searches for text patterns in files using:
- Regular expressions
- File inclusion/exclusion filters
- Ripgrep integration (if available)
"""

import re
import os
import fnmatch
import subprocess
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass

from .tool import BaseTool, ToolDefinition, ToolParameter, ToolResult, ToolStatus, ToolContext


# Configuration constants
MAX_LINE_LENGTH = 2000
MAX_RESULTS = 100


@dataclass
class SearchToolConfig:
    """Configuration for SearchTool."""
    working_dir: Optional[Path] = None
    use_ripgrep: bool = True
    max_results: int = MAX_RESULTS


class SearchTool(BaseTool):
    """Tool for searching text in files (grep-like functionality)."""
    
    def __init__(self, config: Optional[SearchToolConfig] = None):
        self.config = config or SearchToolConfig()
        self.working_dir = self.config.working_dir or Path.cwd()
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search",
            description="Search for text in files using regex patterns",
            parameters=[
                ToolParameter(
                    name="pattern",
                    type="string",
                    description="The regex pattern to search for in file contents",
                    required=True,
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="The directory to search in. Defaults to the current working directory.",
                    required=False,
                ),
                ToolParameter(
                    name="include",
                    type="string",
                    description='File pattern to include in the search (e.g. "*.py", "*.{ts,tsx}")',
                    required=False,
                ),
            ],
        )
    
    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        pattern = kwargs.get("pattern")
        search_path = kwargs.get("path", str(self.working_dir))
        include = kwargs.get("include")
        
        if not pattern:
            return ToolResult(
                tool_name="search",
                status=ToolStatus.ERROR,
                content=None,
                error="pattern is required",
            )
        
        try:
            # Resolve path
            path = Path(search_path)
            if not path.is_absolute():
                path = self.working_dir / path
            
            # Request permission
            await ctx.ask(
                permission="grep",
                patterns=[pattern],
                always=["*"],
                metadata={
                    "pattern": pattern,
                    "path": str(path),
                    "include": include,
                },
            )
            
            # Try ripgrep first if available
            if self.config.use_ripgrep:
                result = await self._search_with_ripgrep(ctx, pattern, path, include)
                if result is not None:
                    return result
            
            # Fall back to Python implementation
            return await self._search_with_python(ctx, pattern, path, include)
            
        except Exception as e:
            return ToolResult(
                tool_name="search",
                status=ToolStatus.ERROR,
                content=None,
                error=str(e),
            )
    
    async def _search_with_ripgrep(
        self,
        ctx: ToolContext,
        pattern: str,
        search_path: Path,
        include: Optional[str],
    ) -> Optional[ToolResult]:
        """Search using ripgrep if available."""
        try:
            # Find ripgrep
            rg_path = self._find_ripgrep()
            if not rg_path:
                return None
            
            # Build command
            args = [
                rg_path,
                "-nH",  # Line numbers, filenames
                "--hidden",  # Search hidden files
                "--no-messages",  # Suppress error messages
                "--field-match-separator=|",
                "--regexp",
                pattern,
            ]
            
            if include:
                args.extend(["--glob", include])
            
            args.append(str(search_path))
            
            # Execute ripgrep
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            
            stdout, stderr = process.communicate(timeout=30)
            exit_code = process.returncode
            
            # Exit codes: 0 = matches found, 1 = no matches, 2 = errors
            if exit_code == 1 or (exit_code == 2 and not stdout.strip()):
                return ToolResult(
                    tool_name="search",
                    status=ToolStatus.SUCCESS,
                    content="No files found",
                    title=pattern,
                    metadata={"matches": 0, "truncated": False},
                )
            
            if exit_code not in (0, 2):
                raise RuntimeError(f"ripgrep failed: {stderr}")
            
            has_errors = exit_code == 2
            
            # Parse output
            matches = self._parse_ripgrep_output(stdout)
            
            # Sort by modification time (most recent first)
            matches.sort(key=lambda m: m.get("modTime", 0), reverse=True)
            
            # Truncate if needed
            truncated = len(matches) > self.config.max_results
            final_matches = matches[:self.config.max_results] if truncated else matches
            
            if not final_matches:
                return ToolResult(
                    tool_name="search",
                    status=ToolStatus.SUCCESS,
                    content="No files found",
                    title=pattern,
                    metadata={"matches": 0, "truncated": False},
                )
            
            # Format output
            output_lines = [
                f"Found {len(matches)} matches" + (f" (showing first {self.config.max_results})" if truncated else "")
            ]
            
            current_file = ""
            for match in final_matches:
                if current_file != match["path"]:
                    if current_file:
                        output_lines.append("")
                    current_file = match["path"]
                    output_lines.append(f"{match['path']}:")
                
                line_text = match["lineText"]
                if len(line_text) > MAX_LINE_LENGTH:
                    line_text = line_text[:MAX_LINE_LENGTH] + "..."
                
                output_lines.append(f"  Line {match['lineNum']}: {line_text}")
            
            if truncated:
                output_lines.append("")
                output_lines.append(
                    f"(Results truncated: showing {self.config.max_results} of {len(matches)} matches "
                    f"({len(matches) - self.config.max_results} hidden). Consider using a more specific path or pattern.)"
                )
            
            if has_errors:
                output_lines.append("")
                output_lines.append("(Some paths were inaccessible and skipped)")
            
            return ToolResult(
                tool_name="search",
                status=ToolStatus.SUCCESS,
                content="\n".join(output_lines),
                title=pattern,
                metadata={
                    "matches": len(matches),
                    "truncated": truncated,
                },
            )
            
        except subprocess.TimeoutExpired:
            return None
        except FileNotFoundError:
            return None
        except Exception:
            return None
    
    def _find_ripgrep(self) -> Optional[str]:
        """Find ripgrep executable."""
        # Try common locations
        paths_to_try = [
            "rg",  # In PATH
            "/usr/bin/rg",
            "/usr/local/bin/rg",
            "/opt/homebrew/bin/rg",
        ]
        
        for path in paths_to_try:
            try:
                result = subprocess.run(
                    [path, "--version"],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    return path
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        
        return None
    
    def _parse_ripgrep_output(self, output: str) -> list[dict]:
        """Parse ripgrep output into structured matches."""
        matches = []
        
        for line in output.strip().split("\n"):
            if not line:
                continue
            
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            
            file_path, line_num_str, line_text = parts
            
            try:
                line_num = int(line_num_str)
            except ValueError:
                continue
            
            # Get modification time
            try:
                mod_time = Path(file_path).stat().st_mtime
            except (OSError, FileNotFoundError):
                mod_time = 0
            
            matches.append({
                "path": file_path,
                "modTime": mod_time,
                "lineNum": line_num,
                "lineText": line_text,
            })
        
        return matches
    
    async def _search_with_python(
        self,
        ctx: ToolContext,
        pattern: str,
        search_path: Path,
        include: Optional[str],
    ) -> ToolResult:
        """Search using Python's built-in capabilities."""
        try:
            # Compile regex
            try:
                regex = re.compile(pattern)
            except re.error as e:
                return ToolResult(
                    tool_name="search",
                    status=ToolStatus.ERROR,
                    content=None,
                    error=f"Invalid regex pattern: {e}",
                )
            
            # Find files to search
            files = self._find_files(search_path, include)
            
            # Search in files
            results = []
            files_searched = 0
            
            for file_path in files:
                if files_searched >= 100:  # Limit files searched
                    break
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                results.append({
                                    "file": str(file_path),
                                    "line": line_num,
                                    "content": line.strip(),
                                })
                                
                                if len(results) >= self.config.max_results:
                                    break
                except (IOError, PermissionError, UnicodeDecodeError):
                    continue
                
                files_searched += 1
                
                if len(results) >= self.config.max_results:
                    break
            
            truncated = len(results) >= self.config.max_results
            
            if not results:
                return ToolResult(
                    tool_name="search",
                    status=ToolStatus.SUCCESS,
                    content="No files found",
                    title=pattern,
                    metadata={"matches": 0, "truncated": False},
                )
            
            # Format output
            output_lines = [
                f"Found {len(results)} matches" + (" (truncated)" if truncated else "")
            ]
            
            current_file = ""
            for result in results:
                if current_file != result["file"]:
                    if current_file:
                        output_lines.append("")
                    current_file = result["file"]
                    output_lines.append(f"{result['file']}:")
                
                content = result["content"]
                if len(content) > MAX_LINE_LENGTH:
                    content = content[:MAX_LINE_LENGTH] + "..."
                
                output_lines.append(f"  Line {result['line']}: {content}")
            
            if truncated:
                output_lines.append("")
                output_lines.append(f"(Results truncated at {self.config.max_results} matches)")
            
            return ToolResult(
                tool_name="search",
                status=ToolStatus.SUCCESS,
                content="\n".join(output_lines),
                title=pattern,
                metadata={
                    "matches": len(results),
                    "truncated": truncated,
                },
            )
            
        except Exception as e:
            return ToolResult(
                tool_name="search",
                status=ToolStatus.ERROR,
                content=None,
                error=str(e),
            )
    
    def _find_files(self, search_path: Path, include: Optional[str]) -> list[Path]:
        """Find files to search."""
        files = []
        
        if search_path.is_file():
            return [search_path]
        
        if not search_path.is_dir():
            return []
        
        try:
            for root, dirs, filenames in os.walk(search_path):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for filename in filenames:
                    # Skip hidden files
                    if filename.startswith('.'):
                        continue
                    
                    file_path = Path(root) / filename
                    
                    # Apply include filter
                    if include:
                        if not self._match_pattern(filename, include):
                            continue
                    
                    files.append(file_path)
        except (PermissionError, OSError):
            pass
        
        return files
    
    def _match_pattern(self, filename: str, pattern: str) -> bool:
        """Match filename against a glob pattern."""
        # Handle multiple patterns (e.g., "*.{ts,tsx}")
        if "{" in pattern and "}" in pattern:
            # Extract patterns from braces
            match = re.search(r'\*\.\{([^}]+)\}', pattern)
            if match:
                extensions = match.group(1).split(",")
                for ext in extensions:
                    if filename.endswith(ext):
                        return True
                return False
        
        return fnmatch.fnmatch(filename, pattern)
