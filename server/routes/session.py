"""
Session routes for OpenCode server.

Provides API endpoints for session management:
- List, create, get, update, delete sessions
- Send messages and commands
- Manage session todos, forks, and compaction
- Handle permissions and sharing
"""

import logging
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Query, Path
from fastapi.responses import JSONResponse, StreamingResponse
import json

from opencode.session import (
    SessionManager,
    SessionInfo,
    MessageWithParts,
    V2AssistantMessage,
    PromptInput,
    prompt,
    get_session,
    create_session,
    get_manager,
    SessionPrompt,
)
from opencode.session.message_v2 import MessageV2Error
from opencode.session.prompt import SessionBusyError
from opencode.agent import get_default_agent
from opencode.provider import get_provider
from opencode.permission import get_permission_manager, PermissionLevel
from opencode.snapshot import FileDiff

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/session", tags=["session"])


# GET /session/ - List sessions
@router.get("/")
async def list_sessions(
    directory: Optional[str] = Query(None, description="Filter sessions by project directory"),
    roots: Optional[bool] = Query(None, description="Only return root sessions (no parentID)"),
    start: Optional[int] = Query(None, description="Filter sessions updated on or after this timestamp (milliseconds since epoch)"),
    search: Optional[str] = Query(None, description="Filter sessions by title (case-insensitive)"),
    limit: Optional[int] = Query(None, description="Maximum number of sessions to return"),
):
    """
    List sessions.
    
    Get a list of all OpenCode sessions, sorted by most recently updated.
    """
    try:
        manager = get_manager()
        sessions = await manager.list_sessions(
            directory=directory,
            roots=roots,
            start=start,
            search=search,
            limit=limit,
        )
        return [session.model_dump() for session in sessions]
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# GET /session/status - Get session status
@router.get("/status")
async def get_session_status():
    """
    Get session status.
    
    Retrieve the current status of all sessions, including active, idle, and completed states.
    """
    try:
        manager = get_manager()
        status = manager.get_session_status()
        return status
    except Exception as e:
        logger.error(f"Error getting session status: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# GET /session/{sessionID} - Get session
@router.get("/{session_id}")
async def get_session_endpoint(session_id: str = Path(..., description="Session ID")):
    """
    Get session.
    
    Retrieve detailed information about a specific OpenCode session.
    """
    try:
        logger.info(f"Getting session: {session_id}")
        session = await get_session(session_id)
        return session.model_dump()
    except Exception as e:
        logger.error(f"Error getting session {session_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=str(e))


# GET /session/{sessionID}/children - Get session children
@router.get("/{session_id}/children")
async def get_session_children(session_id: str = Path(..., description="Session ID")):
    """
    Get session children.
    
    Retrieve all child sessions that were forked from the specified parent session.
    """
    try:
        manager = get_manager()
        children = await manager.get_children(session_id)
        return [child.model_dump() for child in children]
    except Exception as e:
        logger.error(f"Error getting session children {session_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=str(e))


# GET /session/{sessionID}/todo - Get session todos
@router.get("/{session_id}/todo")
async def get_session_todos(session_id: str = Path(..., description="Session ID")):
    """
    Get session todos.
    
    Retrieve the todo list associated with a specific session, showing tasks and action items.
    """
    try:
        manager = get_manager()
        todos = await manager.get_todos(session_id)
        return [todo.model_dump() for todo in todos]
    except Exception as e:
        logger.error(f"Error getting session todos {session_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=str(e))


# POST /session/ - Create session
@router.post("/")
async def create_session_endpoint(body: Optional[Dict[str, Any]] = None):
    """
    Create session.
    
    Create a new OpenCode session for interacting with AI assistants and managing conversations.
    """
    try:
        body = body or {}
        session = await create_session(body)
        return session.model_dump()
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# DELETE /session/{sessionID} - Delete session
@router.delete("/{session_id}")
async def delete_session(session_id: str = Path(..., description="Session ID")):
    """
    Delete session.
    
    Delete a session and permanently remove all associated data, including messages and history.
    """
    try:
        manager = get_manager()
        await manager.delete_session(session_id)
        return True
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=str(e))


# PATCH /session/{sessionID} - Update session
@router.patch("/{session_id}")
async def update_session(
    session_id: str = Path(..., description="Session ID"),
    body: Optional[Dict[str, Any]] = None,
):
    """
    Update session.
    
    Update properties of an existing session, such as title or other metadata.
    """
    try:
        body = body or {}
        manager = get_manager()
        
        session = await get_session(session_id)
        
        if "title" in body and body["title"] is not None:
            session = await manager.set_title(session_id, body["title"])
        
        if "time" in body and body["time"] and "archived" in body["time"]:
            session = await manager.set_archived(session_id, body["time"]["archived"])
        
        return session.model_dump()
    except Exception as e:
        logger.error(f"Error updating session {session_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=str(e))


# POST /session/{sessionID}/init - Initialize session
@router.post("/{session_id}/init")
async def initialize_session(
    session_id: str = Path(..., description="Session ID"),
    body: Optional[Dict[str, Any]] = None,
):
    """
    Initialize session.
    
    Analyze the current application and create an AGENTS.md file with project-specific agent configurations.
    """
    try:
        body = body or {}
        manager = get_manager()
        await manager.initialize_session(session_id, body)
        return True
    except Exception as e:
        logger.error(f"Error initializing session {session_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=str(e))


# POST /session/{sessionID}/fork - Fork session
@router.post("/{session_id}/fork")
async def fork_session(
    session_id: str = Path(..., description="Session ID"),
    body: Optional[Dict[str, Any]] = None,
):
    """
    Fork session.
    
    Create a new session by forking an existing session at a specific message point.
    """
    try:
        body = body or {}
        manager = get_manager()
        result = await manager.fork_session(session_id, body)
        return result.model_dump()
    except Exception as e:
        logger.error(f"Error forking session {session_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /session/{sessionID}/abort - Abort session
@router.post("/{session_id}/abort")
async def abort_session(session_id: str = Path(..., description="Session ID")):
    """
    Abort session.
    
    Abort an active session and stop any ongoing AI processing or command execution.
    """
    try:
        SessionPrompt.cancel(session_id)
        return True
    except Exception as e:
        logger.error(f"Error aborting session {session_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=str(e))


# POST /session/{sessionID}/share - Share session
@router.post("/{session_id}/share")
async def share_session(session_id: str = Path(..., description="Session ID")):
    """
    Share session.
    
    Create a shareable link for a session, allowing others to view the conversation.
    """
    try:
        manager = get_manager()
        await manager.share_session(session_id)
        session = await get_session(session_id)
        return session.model_dump()
    except Exception as e:
        logger.error(f"Error sharing session {session_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=str(e))


# GET /session/{sessionID}/diff - Get message diff
@router.get("/{session_id}/diff")
async def get_message_diff(
    session_id: str = Path(..., description="Session ID"),
    message_id: str = Query(..., description="Message ID"),
):
    """
    Get message diff.
    
    Get the file changes (diff) that resulted from a specific user message in the session.
    """
    try:
        manager = get_manager()
        result = await manager.get_message_diff(session_id, message_id)
        return [diff.model_dump() if hasattr(diff, 'model_dump') else diff for diff in result]
    except Exception as e:
        logger.error(f"Error getting message diff: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# DELETE /session/{sessionID}/share - Unshare session
@router.delete("/{session_id}/share")
async def unshare_session(session_id: str = Path(..., description="Session ID")):
    """
    Unshare session.
    
    Remove the shareable link for a session, making it private again.
    """
    try:
        manager = get_manager()
        await manager.unshare_session(session_id)
        session = await get_session(session_id)
        return session.model_dump()
    except Exception as e:
        logger.error(f"Error unsharing session {session_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=str(e))


# POST /session/{sessionID}/summarize - Summarize session
@router.post("/{session_id}/summarize")
async def summarize_session(
    session_id: str = Path(..., description="Session ID"),
    body: Optional[Dict[str, Any]] = None,
):
    """
    Summarize session.
    
    Generate a concise summary of the session using AI compaction to preserve key information.
    """
    try:
        body = body or {}
        manager = get_manager()
        
        session = await get_session(session_id)
        await manager.cleanup_revert(session)
        
        msgs = await manager.get_messages(session_id)
        
        current_agent = await get_default_agent()
        for i in range(len(msgs) - 1, -1, -1):
            info = msgs[i].info
            if info.role == "user":
                current_agent = info.agent or await get_default_agent()
                break
        
        await manager.create_compaction(
            session_id=session_id,
            agent=current_agent,
            model={
                "provider_id": body.get("provider_id"),
                "model_id": body.get("model_id"),
            },
            auto=body.get("auto", False),
        )
        
        await SessionPrompt.loop(session_id)
        
        return True
    except Exception as e:
        logger.error(f"Error summarizing session {session_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=str(e))


# GET /session/{sessionID}/message - Get session messages
@router.get("/{session_id}/message")
async def get_session_messages(
    session_id: str = Path(..., description="Session ID"),
    limit: Optional[int] = Query(None, description="Maximum number of messages to return"),
):
    """
    Get session messages.
    
    Retrieve all messages in a session, including user prompts and AI responses.
    """
    try:
        manager = get_manager()
        messages = await manager.get_messages(session_id, limit=limit)
        return [msg.model_dump() for msg in messages]
    except Exception as e:
        logger.error(f"Error getting messages for session {session_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=str(e))


# GET /session/{sessionID}/message/{messageID} - Get message
@router.get("/{session_id}/message/{message_id}")
async def get_message(
    session_id: str = Path(..., description="Session ID"),
    message_id: str = Path(..., description="Message ID"),
):
    """
    Get message.
    
    Retrieve a specific message from a session by its message ID.
    """
    try:
        from opencode.session.message_v2 import get_message as get_message_v2
        message = await get_message_v2(session_id, message_id)
        return message
    except Exception as e:
        logger.error(f"Error getting message {message_id} from session {session_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Message not found")
        raise HTTPException(status_code=400, detail=str(e))


# DELETE /session/{sessionID}/message/{messageID}/part/{partID} - Delete part
@router.delete("/{session_id}/message/{message_id}/part/{part_id}")
async def delete_part(
    session_id: str = Path(..., description="Session ID"),
    message_id: str = Path(..., description="Message ID"),
    part_id: str = Path(..., description="Part ID"),
):
    """
    Delete a part from a message.
    """
    try:
        manager = get_manager()
        await manager.remove_part(session_id, message_id, part_id)
        return True
    except Exception as e:
        logger.error(f"Error deleting part {part_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Part not found")
        raise HTTPException(status_code=400, detail=str(e))


# PATCH /session/{sessionID}/message/{messageID}/part/{partID} - Update part
@router.patch("/{session_id}/message/{message_id}/part/{part_id}")
async def update_part(
    session_id: str = Path(..., description="Session ID"),
    message_id: str = Path(..., description="Message ID"),
    part_id: str = Path(..., description="Part ID"),
    body: Optional[Dict[str, Any]] = None,
):
    """
    Update a part in a message.
    """
    try:
        body = body or {}
        if body.get("id") != part_id or body.get("message_id") != message_id or body.get("session_id") != session_id:
            raise ValueError(
                f"Part mismatch: body.id='{body.get('id')}' vs part_id='{part_id}', "
                f"body.message_id='{body.get('message_id')}' vs message_id='{message_id}', "
                f"body.session_id='{body.get('session_id')}' vs session_id='{session_id}'"
            )
        
        manager = get_manager()
        part = await manager.update_part(body)
        return part.model_dump() if hasattr(part, 'model_dump') else part
    except Exception as e:
        logger.error(f"Error updating part {part_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Part not found")
        raise HTTPException(status_code=400, detail=str(e))


# POST /session/{sessionID}/message - Send message (streaming)
@router.post("/{session_id}/message")
async def send_message(
    session_id: str = Path(..., description="Session ID"),
    body: Optional[Dict[str, Any]] = None,
):
    """
    Send message.
    
    Create and send a new message to a session, streaming the AI response.
    """
    try:
        body = body or {}
        
        async def generate():
            msg = await SessionPrompt.prompt(session_id=session_id, **body)
            yield json.dumps(msg if isinstance(msg, dict) else msg.model_dump())
        
        return StreamingResponse(
            generate(),
            media_type="application/json",
        )
    except SessionBusyError:
        raise HTTPException(status_code=409, detail="Session is busy")
    except MessageV2Error as e:
        logger.error(f"Message error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=str(e))


# POST /session/{sessionID}/prompt_async - Send async message
@router.post("/{session_id}/prompt_async", status_code=204)
async def send_message_async(
    session_id: str = Path(..., description="Session ID"),
    body: Optional[Dict[str, Any]] = None,
):
    """
    Send async message.
    
    Create and send a new message to a session asynchronously, starting the session if needed and returning immediately.
    """
    try:
        body = body or {}
        # Fire and forget
        asyncio.create_task(SessionPrompt.prompt(session_id=session_id, **body))
        return None
    except Exception as e:
        logger.error(f"Error sending async message: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=str(e))


# POST /session/{sessionID}/command - Send command
@router.post("/{session_id}/command")
async def send_command(
    session_id: str = Path(..., description="Session ID"),
    body: Optional[Dict[str, Any]] = None,
):
    """
    Send command.
    
    Send a new command to a session for execution by the AI assistant.
    """
    try:
        body = body or {}
        msg = await SessionPrompt.command(session_id=session_id, **body)
        return msg if isinstance(msg, dict) else msg.model_dump()
    except Exception as e:
        logger.error(f"Error sending command: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=str(e))


# POST /session/{sessionID}/shell - Run shell command
@router.post("/{session_id}/shell")
async def run_shell_command(
    session_id: str = Path(..., description="Session ID"),
    body: Optional[Dict[str, Any]] = None,
):
    """
    Run shell command.
    
    Execute a shell command within the session context and return the AI's response.
    """
    try:
        body = body or {}
        msg = await SessionPrompt.shell(session_id=session_id, **body)
        return msg if isinstance(msg, dict) else msg.model_dump()
    except Exception as e:
        logger.error(f"Error running shell command: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=str(e))


# POST /session/{sessionID}/revert - Revert message
@router.post("/{session_id}/revert")
async def revert_message(
    session_id: str = Path(..., description="Session ID"),
    body: Optional[Dict[str, Any]] = None,
):
    """
    Revert message.
    
    Revert a specific message in a session, undoing its effects and restoring the previous state.
    """
    try:
        body = body or {}
        logger.info(f"Reverting message in session {session_id}: {body}")
        manager = get_manager()
        session = await manager.revert(session_id, body)
        return session.model_dump()
    except Exception as e:
        logger.error(f"Error reverting message in session {session_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=str(e))


# POST /session/{sessionID}/unrevert - Restore reverted messages
@router.post("/{session_id}/unrevert")
async def unrevert_messages(session_id: str = Path(..., description="Session ID")):
    """
    Restore reverted messages.
    
    Restore all previously reverted messages in a session.
    """
    try:
        manager = get_manager()
        session = await manager.unrevert(session_id)
        return session.model_dump()
    except Exception as e:
        logger.error(f"Error unreverting messages in session {session_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=str(e))


# POST /session/{sessionID}/permissions/{permissionID} - Respond to permission (deprecated)
@router.post("/{session_id}/permissions/{permission_id}")
async def respond_to_permission(
    session_id: str = Path(..., description="Session ID"),
    permission_id: str = Path(..., description="Permission ID"),
    body: Optional[Dict[str, Any]] = None,
):
    """
    Respond to permission.
    
    Approve or deny a permission request from the AI assistant.
    
    Deprecated: Use /permission/{requestID}/reply instead.
    """
    try:
        body = body or {}
        from opencode.permission import PermissionNext
        await PermissionNext.reply(
            request_id=permission_id,
            reply=body.get("response"),
        )
        return True
    except Exception as e:
        logger.error(f"Error responding to permission {permission_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Permission not found")
        raise HTTPException(status_code=400, detail=str(e))


import asyncio
