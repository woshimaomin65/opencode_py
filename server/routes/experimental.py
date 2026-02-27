"""
Experimental routes for OpenCode server.

Provides API endpoints for experimental features:
- Tool management
- Worktree (git worktree) operations
- MCP resources
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from tool.registry import ToolRegistry
from project import get_project_manager
from mcp import get_mcp_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/experimental", tags=["experimental"])


class WorktreeCreateRequest(BaseModel):
    """Request body for creating a worktree."""
    branch: Optional[str] = None
    directory: Optional[str] = None


class WorktreeRemoveRequest(BaseModel):
    """Request body for removing a worktree."""
    directory: str


class WorktreeResetRequest(BaseModel):
    """Request body for resetting a worktree."""
    directory: str


from pydantic import BaseModel


# Placeholder for Worktree module
class WorktreeManager:
    """Manager for git worktrees."""
    
    @classmethod
    async def create(cls, body: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new worktree."""
        # Implementation depends on git worktree commands
        branch = body.get("branch")
        directory = body.get("directory")
        
        import subprocess
        import os
        
        project_manager = get_project_manager()
        current_project = project_manager.get_current_project()
        
        if not current_project:
            raise ValueError("No current project")
        
        cwd = current_project.directory
        
        # Create worktree
        cmd = ["git", "worktree", "add"]
        if branch:
            cmd.extend(["-b", branch])
        cmd.append(directory or f".worktree/{branch or 'feature'}")
        
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            raise ValueError(f"Failed to create worktree: {result.stderr}")
        
        return {
            "directory": directory or f".worktree/{branch or 'feature'}",
            "branch": branch,
            "status": "created",
        }
    
    @classmethod
    async def remove(cls, body: Dict[str, Any]) -> None:
        """Remove a worktree."""
        directory = body.get("directory")
        
        import subprocess
        
        project_manager = get_project_manager()
        current_project = project_manager.get_current_project()
        
        if not current_project:
            raise ValueError("No current project")
        
        cwd = current_project.directory
        
        # Remove worktree
        cmd = ["git", "worktree", "remove", directory]
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            raise ValueError(f"Failed to remove worktree: {result.stderr}")
    
    @classmethod
    async def reset(cls, body: Dict[str, Any]) -> None:
        """Reset a worktree to the primary branch."""
        directory = body.get("directory")
        
        import subprocess
        
        project_manager = get_project_manager()
        current_project = project_manager.get_current_project()
        
        if not current_project:
            raise ValueError("No current project")
        
        cwd = current_project.directory
        worktree_cwd = os.path.join(cwd, directory)
        
        # Reset to primary branch
        cmd = ["git", "reset", "--hard", "HEAD"]
        result = subprocess.run(cmd, cwd=worktree_cwd, capture_output=True, text=True)
        if result.returncode != 0:
            raise ValueError(f"Failed to reset worktree: {result.stderr}")


# GET /experimental/tool/ids - List tool IDs
@router.get("/tool/ids")
async def list_tool_ids():
    """
    List tool IDs.
    
    Get a list of all available tool IDs, including both built-in tools and dynamically registered tools.
    """
    try:
        registry = ToolRegistry()
        ids = await registry.get_tool_ids()
        return ids
    except Exception as e:
        logger.error(f"Error listing tool IDs: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# GET /experimental/tool - List tools
@router.get("/tool")
async def list_tools(
    provider: str = Query(..., description="Provider ID"),
    model: str = Query(..., description="Model ID"),
):
    """
    List tools.
    
    Get a list of available tools with their JSON schema parameters for a specific provider and model combination.
    """
    try:
        registry = ToolRegistry()
        tools = await registry.get_tools(provider_id=provider, model_id=model)
        
        result = []
        for tool in tools:
            tool_info = {
                "id": tool.id if hasattr(tool, 'id') else tool.get('id'),
                "description": tool.description if hasattr(tool, 'description') else tool.get('description', ''),
                "parameters": tool.parameters if hasattr(tool, 'parameters') else tool.get('parameters', {}),
            }
            result.append(tool_info)
        
        return result
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /experimental/worktree - Create worktree
@router.post("/worktree")
async def create_worktree(body: WorktreeCreateRequest):
    """
    Create worktree.
    
    Create a new git worktree for the current project and run any configured startup scripts.
    """
    try:
        worktree = await WorktreeManager.create(body.model_dump())
        return worktree
    except Exception as e:
        logger.error(f"Error creating worktree: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# GET /experimental/worktree - List worktrees
@router.get("/worktree")
async def list_worktrees():
    """
    List worktrees.
    
    List all sandbox worktrees for the current project.
    """
    try:
        project_manager = get_project_manager()
        current_project = project_manager.get_current_project()
        
        if not current_project:
            return []
        
        sandboxes = await project_manager.get_sandboxes(current_project.id)
        return sandboxes
    except Exception as e:
        logger.error(f"Error listing worktrees: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# DELETE /experimental/worktree - Remove worktree
@router.delete("/worktree")
async def remove_worktree(body: WorktreeRemoveRequest):
    """
    Remove worktree.
    
    Remove a git worktree and delete its branch.
    """
    try:
        await WorktreeManager.remove(body.model_dump())
        
        # Remove from project sandboxes
        project_manager = get_project_manager()
        current_project = project_manager.get_current_project()
        
        if current_project:
            await project_manager.remove_sandbox(current_project.id, body.directory)
        
        return True
    except Exception as e:
        logger.error(f"Error removing worktree: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /experimental/worktree/reset - Reset worktree
@router.post("/worktree/reset")
async def reset_worktree(body: WorktreeResetRequest):
    """
    Reset worktree.
    
    Reset a worktree branch to the primary default branch.
    """
    try:
        await WorktreeManager.reset(body.model_dump())
        return True
    except Exception as e:
        logger.error(f"Error resetting worktree: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# GET /experimental/resource - Get MCP resources
@router.get("/resource")
async def get_mcp_resources():
    """
    Get MCP resources.
    
    Get all available MCP resources from connected servers. Optionally filter by name.
    """
    try:
        manager = get_mcp_manager()
        resources = await manager.get_resources()
        return resources
    except Exception as e:
        logger.error(f"Error getting MCP resources: {e}")
        raise HTTPException(status_code=400, detail=str(e))
