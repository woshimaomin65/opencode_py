"""
Edit tool for OpenCode.

Edits files using various string matching strategies:
- Simple exact match
- Line-trimmed match
- Block anchor match
- Whitespace normalized match
- Indentation flexible match
- And more...
"""

import re
from pathlib import Path
from typing import Optional, Any, Generator
from dataclasses import dataclass
from difflib import unified_diff

from opencode.tool.tool import BaseTool, ToolDefinition, ToolParameter, ToolResult, ToolStatus, ToolContext


@dataclass
class EditToolConfig:
    """Configuration for EditTool."""
    working_dir: Optional[Path] = None


# Similarity thresholds for block anchor fallback matching
SINGLE_CANDIDATE_SIMILARITY_THRESHOLD = 0.0
MULTIPLE_CANDIDATES_SIMILARITY_THRESHOLD = 0.3


class EditTool(BaseTool):
    """Tool for editing files with SEARCH/REPLACE blocks."""
    
    def __init__(self, config: Optional[EditToolConfig] = None):
        self.config = config or EditToolConfig()
        self.working_dir = self.config.working_dir or Path.cwd()
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="edit",
            description="Edit a file using SEARCH/REPLACE blocks",
            parameters=[
                ToolParameter(
                    name="filePath",
                    type="string",
                    description="The absolute path to the file to modify",
                    required=True,
                ),
                ToolParameter(
                    name="oldString",
                    type="string",
                    description="The text to replace",
                    required=True,
                ),
                ToolParameter(
                    name="newString",
                    type="string",
                    description="The text to replace it with (must be different from oldString)",
                    required=True,
                ),
                ToolParameter(
                    name="replaceAll",
                    type="boolean",
                    description="Replace all occurrences of oldString (default false)",
                    required=False,
                ),
            ],
        )
    
    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        file_path = kwargs.get("filePath")
        old_string = kwargs.get("oldString")
        new_string = kwargs.get("newString")
        replace_all = kwargs.get("replaceAll", False)
        
        if not file_path:
            return ToolResult(
                tool_name="edit",
                status=ToolStatus.ERROR,
                content=None,
                error="filePath is required",
            )
        
        if not old_string:
            return ToolResult(
                tool_name="edit",
                status=ToolStatus.ERROR,
                content=None,
                error="oldString is required",
            )
        
        if not new_string:
            return ToolResult(
                tool_name="edit",
                status=ToolStatus.ERROR,
                content=None,
                error="newString is required",
            )
        
        if old_string == new_string:
            return ToolResult(
                tool_name="edit",
                status=ToolStatus.ERROR,
                content=None,
                error="No changes to apply: oldString and newString are identical.",
            )
        
        try:
            # Resolve path
            path = Path(file_path)
            if not path.is_absolute():
                path = self.working_dir / path
            
            # Check if file exists
            if not path.exists():
                return ToolResult(
                    tool_name="edit",
                    status=ToolStatus.ERROR,
                    content=None,
                    error=f"File {path} not found",
                )
            
            if path.is_dir():
                return ToolResult(
                    tool_name="edit",
                    status=ToolStatus.ERROR,
                    content=None,
                    error=f"Path is a directory, not a file: {path}",
                )
            
            # Read file content
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content_old = f.read()
            
            # Apply replacement
            content_new = replace(content_old, old_string, new_string, replace_all)
            
            # Generate diff
            diff = trim_diff(self._generate_diff(str(path), content_old, content_new))
            
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
            
            # Write file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content_new)
            
            # Calculate diff stats
            additions = 0
            deletions = 0
            for line in diff.split('\n'):
                if line.startswith('+') and not line.startswith('+++'):
                    additions += 1
                elif line.startswith('-') and not line.startswith('---'):
                    deletions += 1
            
            # Build output
            output = "Edit applied successfully."
            
            return ToolResult(
                tool_name="edit",
                status=ToolStatus.SUCCESS,
                content=output,
                title=rel_path,
                metadata={
                    "diagnostics": {},
                    "diff": diff,
                    "filediff": {
                        "file": str(path),
                        "before": content_old,
                        "after": content_new,
                        "additions": additions,
                        "deletions": deletions,
                    },
                },
            )
            
        except Exception as e:
            return ToolResult(
                tool_name="edit",
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
        
        return "".join(diff_lines)


def trim_diff(diff: str) -> str:
    """Trim common leading whitespace from diff lines."""
    lines = diff.split("\n")
    content_lines = [
        line for line in lines
        if (line.startswith("+") or line.startswith("-") or line.startswith(" "))
        and not line.startswith("---")
        and not line.startswith("+++")
    ]
    
    if not content_lines:
        return diff
    
    # Find minimum indentation
    min_indent = float('inf')
    for line in content_lines:
        content = line[1:]  # Skip +/- prefix
        if content.strip():
            match = re.match(r'^(\s*)', content)
            if match:
                min_indent = min(min_indent, len(match.group(1)))
    
    if min_indent == float('inf') or min_indent == 0:
        return diff
    
    # Trim indentation
    trimmed_lines = []
    for line in lines:
        if ((line.startswith("+") or line.startswith("-") or line.startswith(" "))
            and not line.startswith("---")
            and not line.startswith("+++")):
            prefix = line[0]
            content = line[1:]
            trimmed_lines.append(prefix + content[min_indent:])
        else:
            trimmed_lines.append(line)
    
    return "\n".join(trimmed_lines)


def replace(content: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """Replace old_string with new_string using multiple strategies."""
    if old_string == new_string:
        raise ValueError("No changes to apply: oldString and newString are identical.")
    
    not_found = True
    
    # Try each replacer strategy
    for replacer in [
        simple_replacer,
        line_trimmed_replacer,
        block_anchor_replacer,
        whitespace_normalized_replacer,
        indentation_flexible_replacer,
        escape_normalized_replacer,
        trimmed_boundary_replacer,
        context_aware_replacer,
        multi_occurrence_replacer,
    ]:
        for search in replacer(content, old_string):
            index = content.find(search)
            if index == -1:
                continue
            
            not_found = False
            
            if replace_all:
                return content.replace(search, new_string)
            
            # Check if unique match
            last_index = content.rfind(search)
            if index != last_index:
                continue
            
            return content[:index] + new_string + content[index + len(search):]
    
    if not_found:
        raise ValueError(
            "Could not find oldString in the file. It must match exactly, including whitespace, indentation, and line endings."
        )
    
    raise ValueError("Found multiple matches for oldString. Provide more surrounding context to make the match unique.")


# Replacer functions (generators that yield potential matches)

def simple_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Simple exact match replacer."""
    yield find


def line_trimmed_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Replacer that matches lines with trimmed whitespace."""
    original_lines = content.split("\n")
    search_lines = find.split("\n")
    
    # Remove trailing empty line
    if search_lines and search_lines[-1] == "":
        search_lines.pop()
    
    for i in range(len(original_lines) - len(search_lines) + 1):
        matches = True
        for j in range(len(search_lines)):
            if original_lines[i + j].strip() != search_lines[j].strip():
                matches = False
                break
        
        if matches:
            # Calculate character indices
            start_idx = sum(len(line) + 1 for line in original_lines[:i])
            end_idx = start_idx + sum(len(original_lines[i + k]) + (1 if k < len(search_lines) - 1 else 0)
                                       for k in range(len(search_lines)))
            yield content[start_idx:end_idx]


def block_anchor_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Replacer that uses first and last lines as anchors."""
    original_lines = content.split("\n")
    search_lines = find.split("\n")
    
    if len(search_lines) < 3:
        return
    
    # Remove trailing empty line
    if search_lines and search_lines[-1] == "":
        search_lines.pop()
    
    first_line = search_lines[0].strip()
    last_line = search_lines[-1].strip()
    
    # Find candidates where both anchors match
    candidates = []
    for i in range(len(original_lines)):
        if original_lines[i].strip() != first_line:
            continue
        
        for j in range(i + 2, len(original_lines)):
            if original_lines[j].strip() == last_line:
                candidates.append((i, j))
                break
    
    if not candidates:
        return
    
    # Single candidate - use relaxed threshold
    if len(candidates) == 1:
        start_line, end_line = candidates[0]
        actual_block_size = end_line - start_line + 1
        search_block_size = len(search_lines)
        
        similarity = calculate_similarity(
            original_lines[start_line + 1:end_line],
            search_lines[1:-1]
        )
        
        if similarity >= SINGLE_CANDIDATE_SIMILARITY_THRESHOLD:
            start_idx = sum(len(line) + 1 for line in original_lines[:start_line])
            end_idx = start_idx + sum(len(original_lines[start_line + k]) + (1 if k < actual_block_size - 1 else 0)
                                       for k in range(actual_block_size))
            yield content[start_idx:end_idx]
        return
    
    # Multiple candidates - pick best match
    best_match = None
    max_similarity = -1
    
    for start_line, end_line in candidates:
        actual_block_size = end_line - start_line + 1
        similarity = calculate_similarity(
            original_lines[start_line + 1:end_line],
            search_lines[1:-1]
        )
        
        if similarity > max_similarity:
            max_similarity = similarity
            best_match = (start_line, end_line)
    
    if best_match and max_similarity >= MULTIPLE_CANDIDATES_SIMILARITY_THRESHOLD:
        start_line, end_line = best_match
        start_idx = sum(len(line) + 1 for line in original_lines[:start_line])
        actual_block_size = end_line - start_line + 1
        end_idx = start_idx + sum(len(original_lines[start_line + k]) + (1 if k < actual_block_size - 1 else 0)
                                   for k in range(actual_block_size))
        yield content[start_idx:end_idx]


def calculate_similarity(lines1: list[str], lines2: list[str]) -> float:
    """Calculate similarity between two lists of lines."""
    if not lines1 or not lines2:
        return 1.0
    
    lines_to_check = min(len(lines1), len(lines2))
    if lines_to_check == 0:
        return 1.0
    
    similarity = 0.0
    for i in range(lines_to_check):
        line1 = lines1[i].strip()
        line2 = lines2[i].strip()
        max_len = max(len(line1), len(line2))
        if max_len > 0:
            distance = levenshtein_distance(line1, line2)
            similarity += (1 - distance / max_len) / lines_to_check
    
    return similarity


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def whitespace_normalized_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Replacer that normalizes whitespace."""
    def normalize(text: str) -> str:
        return ' '.join(text.split())
    
    normalized_find = normalize(find)
    
    # Try single line matches
    lines = content.split("\n")
    for line in lines:
        if normalize(line) == normalized_find:
            yield line
    
    # Try multi-line matches
    find_lines = find.split("\n")
    if len(find_lines) > 1:
        for i in range(len(lines) - len(find_lines) + 1):
            block = "\n".join(lines[i:i + len(find_lines)])
            if normalize(block) == normalized_find:
                yield block


def indentation_flexible_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Replacer that ignores indentation differences."""
    def remove_indentation(text: str) -> str:
        lines = text.split("\n")
        non_empty = [line for line in lines if line.strip()]
        if not non_empty:
            return text
        
        min_indent = min(len(line) - len(line.lstrip()) for line in non_empty)
        return "\n".join(line[min_indent:] if line.strip() else line for line in lines)
    
    normalized_find = remove_indentation(find)
    find_lines = find.split("\n")
    content_lines = content.split("\n")
    
    for i in range(len(content_lines) - len(find_lines) + 1):
        block = "\n".join(content_lines[i:i + len(find_lines)])
        if remove_indentation(block) == normalized_find:
            yield block


def escape_normalized_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Replacer that handles escape sequences."""
    def unescape(text: str) -> str:
        replacements = {
            '\\n': '\n', '\\t': '\t', '\\r': '\r',
            "\\'": "'", '\\"': '"', '\\`': '`', '\\\\': '\\', '\\$': '$',
        }
        for esc, char in replacements.items():
            text = text.replace(esc, char)
        return text
    
    unescaped_find = unescape(find)
    
    if unescaped_find in content:
        yield unescaped_find
    
    # Try finding escaped versions
    lines = content.split("\n")
    find_lines = unescaped_find.split("\n")
    
    for i in range(len(lines) - len(find_lines) + 1):
        block = "\n".join(lines[i:i + len(find_lines)])
        if unescape(block) == unescaped_find:
            yield block


def trimmed_boundary_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Replacer that handles trimmed boundaries."""
    trimmed_find = find.strip()
    
    if trimmed_find == find:
        return
    
    if trimmed_find in content:
        yield trimmed_find
    
    # Try finding blocks where trimmed content matches
    lines = content.split("\n")
    find_lines = find.split("\n")
    
    for i in range(len(lines) - len(find_lines) + 1):
        block = "\n".join(lines[i:i + len(find_lines)])
        if block.strip() == trimmed_find:
            yield block


def context_aware_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Replacer that uses context awareness."""
    find_lines = find.split("\n")
    if len(find_lines) < 3:
        return
    
    # Remove trailing empty line
    if find_lines and find_lines[-1] == "":
        find_lines.pop()
    
    content_lines = content.split("\n")
    first_line = find_lines[0].strip()
    last_line = find_lines[-1].strip()
    
    for i in range(len(content_lines)):
        if content_lines[i].strip() != first_line:
            continue
        
        for j in range(i + 2, len(content_lines)):
            if content_lines[j].strip() != last_line:
                continue
            
            block_lines = content_lines[i:j + 1]
            if len(block_lines) == len(find_lines):
                # Check similarity of middle content
                matching = 0
                total = 0
                for k in range(1, len(block_lines) - 1):
                    if block_lines[k].strip() or find_lines[k].strip():
                        total += 1
                        if block_lines[k].strip() == find_lines[k].strip():
                            matching += 1
                
                if total == 0 or matching / total >= 0.5:
                    yield "\n".join(block_lines)
                    return


def multi_occurrence_replacer(content: str, find: str) -> Generator[str, None, None]:
    """Replacer that finds all occurrences."""
    start_index = 0
    while True:
        index = content.find(find, start_index)
        if index == -1:
            break
        yield find
        start_index = index + len(find)
