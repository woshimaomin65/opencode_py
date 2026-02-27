"""
Permission routes for OpenCode server.

Provides API endpoints for permission management:
- List pending permissions
- Respond to permission requests
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Path

from ..permission import PermissionManager, get_permission_manager, PermissionLevel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/permission", tags=["permission"])


class PermissionReplyRequest(BaseModel):
    """Request body for permission reply."""
    reply: str  # "approve" or "deny"
    message: Optional[str] = None


from pydantic import BaseModel


# POST /permission/{requestID}/reply - Respond to permission request
@router.post("/{request_id}/reply")
async def reply_to_permission(
    request_id: str = Path(..., description="Permission request ID"),
    body: PermissionReplyRequest = None,
):
    """
    Respond to permission request.
    
    Approve or deny a permission request from the AI assistant.
    """
    try:
        manager = get_permission_manager()
        await manager.reply(
            request_id=request_id,
            reply=PermissionLevel.APPROVE if body.reply == "approve" else PermissionLevel.DENY,
            message=body.message,
        )
        return True
    except Exception as e:
        logger.error(f"Error responding to permission {request_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Permission request not found")
        raise HTTPException(status_code=400, detail=str(e))


# GET /permission/ - List pending permissions
@router.get("/")
async def list_permissions():
    """
    List pending permissions.
    
    Get all pending permission requests across all sessions.
    """
    try:
        manager = get_permission_manager()
        permissions = await manager.list_pending()
        return [p.model_dump() if hasattr(p, 'model_dump') else p for p in permissions]
    except Exception as e:
        logger.error(f"Error listing permissions: {e}")
        raise HTTPException(status_code=400, detail=str(e))
