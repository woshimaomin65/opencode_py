"""
MCP (Model Context Protocol) routes for OpenCode server.

Provides API endpoints for MCP server management:
- Get MCP status
- Add/connect/disconnect MCP servers
- Handle OAuth authentication for MCP servers
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel

from mcp import MCPManager, MCPServerConfig, get_mcp_manager
from config import Config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"])


class MCPAddRequest(BaseModel):
    """Request body for adding an MCP server."""
    name: str
    config: Dict[str, Any]


class MCPAuthCallbackRequest(BaseModel):
    """Request body for MCP OAuth callback."""
    code: str


class MCPAuthMethodRequest(BaseModel):
    """Request body for MCP auth method selection."""
    method: int


class MCPAuthStartResponse(BaseModel):
    """Response for starting OAuth flow."""
    authorization_url: str


class MCPAuthRemoveResponse(BaseModel):
    """Response for removing OAuth credentials."""
    success: bool = True


# GET /mcp/ - Get MCP status
@router.get("/")
async def get_mcp_status():
    """
    Get MCP status.
    
    Get the status of all Model Context Protocol (MCP) servers.
    """
    try:
        manager = get_mcp_manager()
        status = await manager.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting MCP status: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /mcp/ - Add MCP server
@router.post("/")
async def add_mcp_server(body: MCPAddRequest):
    """
    Add MCP server.
    
    Dynamically add a new Model Context Protocol (MCP) server to the system.
    """
    try:
        manager = get_mcp_manager()
        config = MCPServerConfig(**body.config)
        result = await manager.add_server(body.name, config)
        return result.status
    except Exception as e:
        logger.error(f"Error adding MCP server {body.name}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /mcp/{name}/auth - Start MCP OAuth
@router.post("/{name}/auth")
async def start_mcp_oauth(name: str = Path(..., description="MCP server name")):
    """
    Start MCP OAuth.
    
    Start OAuth authentication flow for a Model Context Protocol (MCP) server.
    """
    try:
        manager = get_mcp_manager()
        supports_oauth = await manager.supports_oauth(name)
        if not supports_oauth:
            raise HTTPException(
                status_code=400,
                detail=f"MCP server {name} does not support OAuth"
            )
        
        result = await manager.start_auth(name)
        return MCPAuthStartResponse(authorization_url=result.get("authorization_url", ""))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting OAuth for MCP server {name}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="MCP server not found")
        raise HTTPException(status_code=400, detail=str(e))


# POST /mcp/{name}/auth/callback - Complete MCP OAuth
@router.post("/{name}/auth/callback")
async def complete_mcp_oauth(
    name: str = Path(..., description="MCP server name"),
    body: MCPAuthCallbackRequest = None,
):
    """
    Complete MCP OAuth.
    
    Complete OAuth authentication for a Model Context Protocol (MCP) server using the authorization code.
    """
    try:
        manager = get_mcp_manager()
        status = await manager.finish_auth(name, body.code)
        return status
    except Exception as e:
        logger.error(f"Error completing OAuth for MCP server {name}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="MCP server not found")
        raise HTTPException(status_code=400, detail=str(e))


# POST /mcp/{name}/auth/authenticate - Authenticate MCP OAuth
@router.post("/{name}/auth/authenticate")
async def authenticate_mcp_oauth(name: str = Path(..., description="MCP server name")):
    """
    Authenticate MCP OAuth.
    
    Start OAuth flow and wait for callback (opens browser).
    """
    try:
        manager = get_mcp_manager()
        supports_oauth = await manager.supports_oauth(name)
        if not supports_oauth:
            raise HTTPException(
                status_code=400,
                detail=f"MCP server {name} does not support OAuth"
            )
        
        status = await manager.authenticate(name)
        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error authenticating MCP server {name}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="MCP server not found")
        raise HTTPException(status_code=400, detail=str(e))


# DELETE /mcp/{name}/auth - Remove MCP OAuth
@router.delete("/{name}/auth")
async def remove_mcp_oauth(name: str = Path(..., description="MCP server name")):
    """
    Remove MCP OAuth.
    
    Remove OAuth credentials for an MCP server.
    """
    try:
        manager = get_mcp_manager()
        await manager.remove_auth(name)
        return MCPAuthRemoveResponse()
    except Exception as e:
        logger.error(f"Error removing OAuth for MCP server {name}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="MCP server not found")
        raise HTTPException(status_code=400, detail=str(e))


# POST /mcp/{name}/connect - Connect MCP server
@router.post("/{name}/connect")
async def connect_mcp_server(name: str = Path(..., description="MCP server name")):
    """
    Connect an MCP server.
    """
    try:
        manager = get_mcp_manager()
        await manager.connect(name)
        return True
    except Exception as e:
        logger.error(f"Error connecting MCP server {name}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /mcp/{name}/disconnect - Disconnect MCP server
@router.post("/{name}/disconnect")
async def disconnect_mcp_server(name: str = Path(..., description="MCP server name")):
    """
    Disconnect an MCP server.
    """
    try:
        manager = get_mcp_manager()
        await manager.disconnect(name)
        return True
    except Exception as e:
        logger.error(f"Error disconnecting MCP server {name}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
