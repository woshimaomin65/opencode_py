"""
Server Routes module for OpenCode.

Provides FastAPI router definitions for all API endpoints.
"""

from .session import router as session_router
from .mcp import router as mcp_router
from .file import router as file_router
from .config import router as config_router
from .provider import router as provider_router
from .global_routes import router as global_router
from .project import router as project_router
from .permission import router as permission_router
from .question import router as question_router
from .experimental import router as experimental_router
from .tui import router as tui_router
from .pty import router as pty_router

__all__ = [
    "session_router",
    "mcp_router",
    "file_router",
    "config_router",
    "provider_router",
    "global_router",
    "project_router",
    "permission_router",
    "question_router",
    "experimental_router",
    "tui_router",
    "pty_router",
]
