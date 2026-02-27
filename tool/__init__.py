"""Tool module for OpenCode."""

from opencode.tool.tool import (
    BaseTool,
    ToolDefinition,
    ToolParameter,
    ToolResult,
    ToolStatus,
    ToolContext,
    ToolRegistry,
    init_default_tools,
)

from opencode.tool.read import ReadTool, ReadToolConfig
from opencode.tool.write import WriteTool, WriteToolConfig
from opencode.tool.edit import EditTool, EditToolConfig
from opencode.tool.bash import BashTool, BashToolConfig
from opencode.tool.search import SearchTool, SearchToolConfig
from opencode.tool.web import (
    WebSearchTool,
    WebFetchTool,
    WebSearchToolConfig,
    WebFetchToolConfig,
)
from opencode.tool.lsp import LspTool, LspToolConfig, LSPDiagnostic
from opencode.tool.exit import (
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
