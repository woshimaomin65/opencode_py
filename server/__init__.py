"""
Server module for OpenCode.

Provides FastAPI server implementation with all route modules.
"""

from opencode.server.routes import (
    session_router,
    mcp_router,
    file_router,
    config_router,
    provider_router,
    global_router,
    project_router,
    permission_router,
    question_router,
    experimental_router,
    tui_router,
    pty_router,
)


def create_app():
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    
    app = FastAPI(
        title="OpenCode Server",
        description="OpenCode API Server for AI-assisted coding",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include all routers
    app.include_router(session_router)
    app.include_router(mcp_router)
    app.include_router(file_router)
    app.include_router(config_router)
    app.include_router(provider_router)
    app.include_router(global_router)
    app.include_router(project_router)
    app.include_router(permission_router)
    app.include_router(question_router)
    app.include_router(experimental_router)
    app.include_router(tui_router)
    app.include_router(pty_router)
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}
    
    return app


__all__ = ["create_app"]
