"""Tool module for OpenCode."""

from tool.tool import (
    BaseTool,
    ToolDefinition,
    ToolParameter,
    ToolResult,
    ToolStatus,
    ToolContext,
    ToolRegistry,
    init_default_tools,
)

from tool.read import ReadTool, ReadToolConfig
from tool.write import WriteTool, WriteToolConfig
from tool.edit import EditTool, EditToolConfig
from tool.bash import BashTool, BashToolConfig
from tool.search import SearchTool, SearchToolConfig
from tool.web import (
    WebSearchTool,
    WebFetchTool,
    WebSearchToolConfig,
    WebFetchToolConfig,
)
from tool.lsp import LspTool, LspToolConfig, LSPDiagnostic
from tool.exit import (
    ExitTool,
    ExitToolConfig,
    ExitStatus,
    PlanEnterTool,
    PlanExitTool,
)

__all__ = [
    # Base classes
    "BaseTool",
    "ToolDefinition",
    "ToolParameter",
    "ToolResult",
    "ToolStatus",
    "ToolContext",
    "ToolRegistry",
    # Core tools
    "ReadTool",
    "ReadToolConfig",
    "WriteTool",
    "WriteToolConfig",
    "EditTool",
    "EditToolConfig",
    "BashTool",
    "BashToolConfig",
    "SearchTool",
    "SearchToolConfig",
    # Web tools
    "WebSearchTool",
    "WebFetchTool",
    "WebSearchToolConfig",
    "WebFetchToolConfig",
    # LSP tools
    "LspTool",
    "LspToolConfig",
    "LSPDiagnostic",
    # Exit tools
    "ExitTool",
    "ExitToolConfig",
    "ExitStatus",
    "PlanEnterTool",
    "PlanExitTool",
    # Initialization
    "init_default_tools",
]
