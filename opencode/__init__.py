"""
OpenCode - AI-powered coding assistant

Python port of the opencode project.
"""

__version__ = "0.1.0"
__author__ = "OpenCode Contributors"

# Core modules
from .config import Config
from .provider import BaseProvider, get_provider
from .session import Session, SessionManager
from .agent import Agent
from .tool import BaseTool, ToolRegistry

# Additional modules
from .permission import PermissionManager
from .mcp import MCPServer, MCPManager
from .acp import ACPServer, ACPClient
from .lsp import LSPClient, LSPManager
from .project import ProjectManager, get_project_manager
from .file import read_file, write_file
from .shell import run_command, ShellExecutor
from .env import get_env, get_api_key
from .id import generate_id, generate_session_id
from .format import format_duration, format_bytes
from .util import md5_hash, normalize_path

__all__ = [
    # Core
    "Config",
    "BaseProvider",
    "get_provider",
    "Session",
    "SessionManager",
    "Agent",
    "BaseTool",
    "ToolRegistry",
    # Additional
    "PermissionManager",
    "MCPServer",
    "MCPManager",
    "ACPServer",
    "ACPClient",
    "LSPClient",
    "LSPManager",
    "ProjectManager",
    "get_project_manager",
    # Utilities
    "read_file",
    "write_file",
    "run_command",
    "ShellExecutor",
    "get_env",
    "get_api_key",
    "generate_id",
    "generate_session_id",
    "format_duration",
    "format_bytes",
    "md5_hash",
    "normalize_path",
]
