"""
Server Routes module for OpenCode.

Provides FastAPI router definitions for all API endpoints.
"""

from server.routes.session import router as session_router
from server.routes.mcp import router as mcp_router
from server.routes.file import router as file_router
from server.routes.config import router as config_router
from server.routes.provider import router as provider_router
from server.routes.global_routes import router as global_router
from server.routes.project import router as project_router
from server.routes.permission import router as permission_router
from server.routes.question import router as question_router
from server.routes.experimental import router as experimental_router
from server.routes.tui import router as tui_router
from server.routes.pty import router as pty_router

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
