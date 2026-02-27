"""
Server Routes module for OpenCode.

Provides FastAPI router definitions for all API endpoints.
"""

from opencode.server.routes.session import router as session_router
from opencode.server.routes.mcp import router as mcp_router
from opencode.server.routes.file import router as file_router
from opencode.server.routes.config import router as config_router
from opencode.server.routes.provider import router as provider_router
from opencode.server.routes.global_routes import router as global_router
from opencode.server.routes.project import router as project_router
from opencode.server.routes.permission import router as permission_router
from opencode.server.routes.question import router as question_router
from opencode.server.routes.experimental import router as experimental_router
from opencode.server.routes.tui import router as tui_router
from opencode.server.routes.pty import router as pty_router

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
