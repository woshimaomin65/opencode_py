"""
LSP (Language Server Protocol) tool for OpenCode.

Provides LSP operations:
- goToDefinition
- findReferences
- hover
- documentSymbol
- workspaceSymbol
- goToImplementation
- prepareCallHierarchy
- incomingCalls
- outgoingCalls
"""

import json
from pathlib import Path
from typing import Optional, Any, List, Dict
from dataclasses import dataclass
from urllib.parse import quote

from opencode.tool.tool import BaseTool, ToolDefinition, ToolParameter, ToolResult, ToolStatus, ToolContext


# LSP operations
LSP_OPERATIONS = [
    "goToDefinition",
    "findReferences",
    "hover",
    "documentSymbol",
    "workspaceSymbol",
    "goToImplementation",
    "prepareCallHierarchy",
    "incomingCalls",
    "outgoingCalls",
]


@dataclass
class LspToolConfig:
    """Configuration for LspTool."""
    working_dir: Optional[Path] = None


class LspTool(BaseTool):
    """Tool for LSP operations."""
    
    def __init__(self, config: Optional[LspToolConfig] = None):
        self.config = config or LspToolConfig()
        self.working_dir = self.config.working_dir or Path.cwd()
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="lsp",
            description="Perform LSP (Language Server Protocol) operations on code",
            parameters=[
                ToolParameter(
                    name="operation",
                    type="string",
                    description="The LSP operation to perform",
                    required=True,
                    enum=LSP_OPERATIONS,
                ),
                ToolParameter(
                    name="filePath",
                    type="string",
                    description="The absolute or relative path to the file",
                    required=True,
                ),
                ToolParameter(
                    name="line",
                    type="number",
                    description="The line number (1-based, as shown in editors)",
                    required=True,
                ),
                ToolParameter(
                    name="character",
                    type="number",
                    description="The character offset (1-based, as shown in editors)",
                    required=True,
                ),
            ],
        )
    
    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        operation = kwargs.get("operation")
        file_path = kwargs.get("filePath")
        line = kwargs.get("line")
        character = kwargs.get("character")
        
        if not operation:
            return ToolResult(
                tool_name="lsp",
                status=ToolStatus.ERROR,
                content=None,
                error="Missing required parameter: operation",
            )
        
        if operation not in LSP_OPERATIONS:
            return ToolResult(
                tool_name="lsp",
                status=ToolStatus.ERROR,
                content=None,
                error=f"Invalid operation: {operation}. Must be one of {LSP_OPERATIONS}",
            )
        
        if not file_path:
            return ToolResult(
                tool_name="lsp",
                status=ToolStatus.ERROR,
                content=None,
                error="Missing required parameter: filePath",
            )
        
        if not line or not isinstance(line, int) or line < 1:
            return ToolResult(
                tool_name="lsp",
                status=ToolStatus.ERROR,
                content=None,
                error="line must be a positive integer",
            )
        
        if not character or not isinstance(character, int) or character < 1:
            return ToolResult(
                tool_name="lsp",
                status=ToolStatus.ERROR,
                content=None,
                error="character must be a positive integer",
            )
        
        try:
            # Resolve path
            path = Path(file_path)
            if not path.is_absolute():
                path = self.working_dir / path
            
            # Request permission
            await ctx.ask(
                permission="lsp",
                patterns=["*"],
                always=["*"],
                metadata={},
            )
            
            # Check if file exists
            if not path.exists():
                return ToolResult(
                    tool_name="lsp",
                    status=ToolStatus.ERROR,
                    content=None,
                    error=f"File not found: {path}",
                )
            
            # Check if LSP is available for this file type
            if not self._has_lsp_support(path):
                return ToolResult(
                    tool_name="lsp",
                    status=ToolStatus.ERROR,
                    content=None,
                    error="No LSP server available for this file type.",
                )
            
            # Build URI
            uri = path.as_uri()
            
            # Convert to LSP position (0-based)
            position = {
                "file": str(path),
                "line": line - 1,
                "character": character - 1,
            }
            
            # Build title
            try:
                rel_path = path.relative_to(self.working_dir)
            except ValueError:
                rel_path = path
            
            title = f"{operation} {rel_path}:{line}:{character}"
            
            # Execute LSP operation
            result = await self._execute_operation(operation, uri, position)
            
            # Format output
            if not result:
                output = f"No results found for {operation}"
            else:
                output = json.dumps(result, indent=2, default=str)
            
            return ToolResult(
                tool_name="lsp",
                status=ToolStatus.SUCCESS,
                content=output,
                title=title,
                metadata={"result": result},
            )
            
        except Exception as e:
            return ToolResult(
                tool_name="lsp",
                status=ToolStatus.ERROR,
                content=None,
                error=str(e),
            )
    
    def _has_lsp_support(self, path: Path) -> bool:
        """Check if LSP is available for this file type."""
        # Check file extension
        supported_extensions = {
            # Languages with common LSP servers
            '.py', '.js', '.ts', '.jsx', '.tsx',  # JavaScript/TypeScript/Python
            '.go', '.rs', '.java', '.cpp', '.c', '.h', '.hpp',  # Compiled languages
            '.rb', '.php', '.swift', '.kt', '.scala',  # Other popular languages
            '.cs', '.fs', '.fsx',  # .NET languages
            '.html', '.css', '.scss', '.less',  # Web
            '.json', '.yaml', '.yml', '.toml', '.xml',  # Config
            '.md', '.rst',  # Documentation
            '.sql', '.sh', '.bash',  # Scripts
            '.lua', '.vim', '.ex', '.exs',  # Other
        }
        
        return path.suffix.lower() in supported_extensions
    
    async def _execute_operation(
        self,
        operation: str,
        uri: str,
        position: dict,
    ) -> list:
        """Execute an LSP operation.
        
        Note: This is a stub implementation. In a real implementation,
        this would communicate with an actual LSP server.
        """
        # This would integrate with an actual LSP client
        # For now, return empty result
        return []
        
        # Example of what a real implementation might look like:
        # lsp_client = self._get_lsp_client(position["file"])
        # if not lsp_client:
        #     return []
        # 
        # if operation == "goToDefinition":
        #     return await lsp_client.definition(uri, position)
        # elif operation == "findReferences":
        #     return await lsp_client.references(uri, position)
        # elif operation == "hover":
        #     return await lsp_client.hover(uri, position)
        # elif operation == "documentSymbol":
        #     return await lsp_client.document_symbol(uri)
        # elif operation == "workspaceSymbol":
        #     return await lsp_client.workspace_symbol("")
        # elif operation == "goToImplementation":
        #     return await lsp_client.implementation(uri, position)
        # elif operation == "prepareCallHierarchy":
        #     return await lsp_client.prepare_call_hierarchy(uri, position)
        # elif operation == "incomingCalls":
        #     return await lsp_client.incoming_calls(uri, position)
        # elif operation == "outgoingCalls":
        #     return await lsp_client.outgoing_calls(uri, position)
        # 
        # return []
    
    def _get_lsp_client(self, file_path: str) -> Optional[Any]:
        """Get LSP client for a file.
        
        Note: This is a stub. Real implementation would manage LSP server processes.
        """
        return None


# LSP Diagnostic helper
class LSPDiagnostic:
    """Helper class for LSP diagnostics."""
    
    @staticmethod
    def pretty(diagnostic: dict) -> str:
        """Format a diagnostic for display."""
        severity_map = {
            1: "error",
            2: "warning",
            3: "information",
            4: "hint",
        }
        
        severity = severity_map.get(diagnostic.get("severity", 1), "error")
        line = diagnostic.get("range", {}).get("start", {}).get("line", 0) + 1
        character = diagnostic.get("range", {}).get("start", {}).get("character", 0) + 1
        message = diagnostic.get("message", "")
        source = diagnostic.get("source", "")
        
        result = f"[{severity}] {line}:{character}: {message}"
        if source:
            result += f" [{source}]"
        
        return result
