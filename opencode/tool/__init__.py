"""Tool module for OpenCode."""

from .tool import (
    BaseTool,
    ToolDefinition,
    ToolParameter,
    ToolResult,
    ToolStatus,
    ToolContext,
    ToolRegistry,
    init_default_tools,
)

from .read import ReadTool, ReadToolConfig
from .write import WriteTool, WriteToolConfig
from .edit import EditTool, EditToolConfig
from .bash import BashTool, BashToolConfig
from .search import SearchTool, SearchToolConfig
from .web import (
    WebSearchTool,
    WebFetchTool,
    WebSearchToolConfig,
    WebFetchToolConfig,
)
from .lsp import LspTool, LspToolConfig, LSPDiagnostic
from .exit import (
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
