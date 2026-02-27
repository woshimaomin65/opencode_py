"""
Project routes for OpenCode server.

Provides API endpoints for project management:
- List all projects
- Get current project
- Update project properties
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Path

from project import ProjectManager, ProjectInfo, get_project_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/project", tags=["project"])


# GET /project/ - List all projects
@router.get("/")
async def list_projects():
    """
    List all projects.
    
    Get a list of projects that have been opened with OpenCode.
    """
    try:
        manager = get_project_manager()
        projects = await manager.list_projects()
        return [p.model_dump() if hasattr(p, 'model_dump') else p for p in projects]
    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# GET /project/current - Get current project
@router.get("/current")
async def get_current_project():
    """
    Get current project.
    
    Retrieve the currently active project that OpenCode is working with.
    """
    try:
        manager = get_project_manager()
        project = manager.get_current_project()
        if not project:
            raise HTTPException(status_code=404, detail="No current project")
        return project.model_dump() if hasattr(project, 'model_dump') else project
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current project: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# PATCH /project/{projectID} - Update project
@router.patch("/{project_id}")
async def update_project(
    project_id: str = Path(..., description="Project ID"),
    body: Optional[Dict[str, Any]] = None,
):
    """
    Update project.
    
    Update project properties such as name, icon, and commands.
    """
    try:
        body = body or {}
        manager = get_project_manager()
        
        # Extract updatable fields
        update_data = {
            "name": body.get("name"),
            "icon": body.get("icon"),
            "commands": body.get("commands"),
        }
        
        # Remove None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        project = await manager.update_project(project_id, update_data)
        return project.model_dump() if hasattr(project, 'model_dump') else project
    except Exception as e:
        logger.error(f"Error updating project {project_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Project not found")
        raise HTTPException(status_code=400, detail=str(e))
