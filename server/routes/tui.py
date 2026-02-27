"""
TUI (Terminal User Interface) routes for OpenCode server.

Provides API endpoints for TUI control:
- TUI event publishing
- Command execution
- Session and dialog management
- TUI control queue
"""

import logging
import asyncio
from typing import Any, Dict, Optional, List
from collections import deque

from fastapi import APIRouter, HTTPException

from bus import Bus, BusEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tui", tags=["tui"])


# Async queue for TUI requests
class AsyncQueue:
    """Async queue for TUI request/response handling."""
    
    def __init__(self):
        self._queue = deque()
        self._event = asyncio.Event()
    
    async def push(self, item: Any) -> None:
        """Add item to queue."""
        self._queue.append(item)
        self._event.set()
    
    async def next(self) -> Any:
        """Get next item from queue."""
        while not self._queue:
            await self._event.wait()
            self._event.clear()
        
        return self._queue.popleft()


# Request and response queues
_tui_request_queue = AsyncQueue()
_tui_response_queue = AsyncQueue()


# TUI event definitions
class TuiEvent:
    """TUI event definitions."""
    
    @staticmethod
    def define(event_type: str, properties_schema: type) -> BusEvent:
        return BusEvent.define(event_type, properties_schema)


# Define TUI events
PromptAppendEvent = BusEvent.define("tui.prompt.append", Dict[str, Any])
ToastShowEvent = BusEvent.define("tui.toast.show", Dict[str, Any])
SessionSelectEvent = BusEvent.define("tui.session.select", Dict[str, Any])
CommandExecuteEvent = BusEvent.define("tui.command.execute", Dict[str, Any])


# POST /tui/append-prompt - Append TUI prompt
@router.post("/append-prompt")
async def append_prompt(body: Dict[str, Any]):
    """
    Append TUI prompt.
    
    Append prompt to the TUI.
    """
    try:
        await Bus.publish(PromptAppendEvent, body)
        return True
    except Exception as e:
        logger.error(f"Error appending prompt: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /tui/open-help - Open help dialog
@router.post("/open-help")
async def open_help():
    """
    Open help dialog.
    
    Open the help dialog in the TUI to display user assistance information.
    """
    try:
        await Bus.publish(CommandExecuteEvent, {"command": "help.show"})
        return True
    except Exception as e:
        logger.error(f"Error opening help: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /tui/open-sessions - Open sessions dialog
@router.post("/open-sessions")
async def open_sessions():
    """
    Open sessions dialog.
    
    Open the session dialog.
    """
    try:
        await Bus.publish(CommandExecuteEvent, {"command": "session.list"})
        return True
    except Exception as e:
        logger.error(f"Error opening sessions: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /tui/open-themes - Open themes dialog
@router.post("/open-themes")
async def open_themes():
    """
    Open themes dialog.
    
    Open the theme dialog.
    """
    try:
        await Bus.publish(CommandExecuteEvent, {"command": "theme.list"})
        return True
    except Exception as e:
        logger.error(f"Error opening themes: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /tui/open-models - Open models dialog
@router.post("/open-models")
async def open_models():
    """
    Open models dialog.
    
    Open the model dialog.
    """
    try:
        await Bus.publish(CommandExecuteEvent, {"command": "model.list"})
        return True
    except Exception as e:
        logger.error(f"Error opening models: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /tui/submit-prompt - Submit TUI prompt
@router.post("/submit-prompt")
async def submit_prompt():
    """
    Submit TUI prompt.
    
    Submit the prompt.
    """
    try:
        await Bus.publish(CommandExecuteEvent, {"command": "prompt.submit"})
        return True
    except Exception as e:
        logger.error(f"Error submitting prompt: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /tui/clear-prompt - Clear TUI prompt
@router.post("/clear-prompt")
async def clear_prompt():
    """
    Clear TUI prompt.
    
    Clear the prompt.
    """
    try:
        await Bus.publish(CommandExecuteEvent, {"command": "prompt.clear"})
        return True
    except Exception as e:
        logger.error(f"Error clearing prompt: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Command mapping for execute-command
COMMAND_MAP = {
    "session_new": "session.new",
    "session_share": "session.share",
    "session_interrupt": "session.interrupt",
    "session_compact": "session.compact",
    "messages_page_up": "session.page.up",
    "messages_page_down": "session.page.down",
    "messages_line_up": "session.line.up",
    "messages_line_down": "session.line.down",
    "messages_half_page_up": "session.half.page.up",
    "messages_half_page_down": "session.half.page.down",
    "messages_first": "session.first",
    "messages_last": "session.last",
    "agent_cycle": "agent.cycle",
}


# POST /tui/execute-command - Execute TUI command
@router.post("/execute-command")
async def execute_command(body: Dict[str, str]):
    """
    Execute TUI command.
    
    Execute a TUI command (e.g. agent_cycle).
    """
    try:
        command = body.get("command", "")
        mapped_command = COMMAND_MAP.get(command, command)
        
        await Bus.publish(CommandExecuteEvent, {"command": mapped_command})
        return True
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /tui/show-toast - Show TUI toast
@router.post("/show-toast")
async def show_toast(body: Dict[str, Any]):
    """
    Show TUI toast.
    
    Show a toast notification in the TUI.
    """
    try:
        await Bus.publish(ToastShowEvent, body)
        return True
    except Exception as e:
        logger.error(f"Error showing toast: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /tui/publish - Publish TUI event
@router.post("/publish")
async def publish_event(body: Dict[str, Any]):
    """
    Publish TUI event.
    
    Publish a TUI event.
    """
    try:
        event_type = body.get("type")
        properties = body.get("properties", {})
        
        # Find matching event definition
        event_map = {
            "tui.prompt.append": PromptAppendEvent,
            "tui.toast.show": ToastShowEvent,
            "tui.session.select": SessionSelectEvent,
            "tui.command.execute": CommandExecuteEvent,
        }
        
        event = event_map.get(event_type)
        if not event:
            raise ValueError(f"Unknown event type: {event_type}")
        
        await Bus.publish(event, properties)
        return True
    except Exception as e:
        logger.error(f"Error publishing event: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /tui/select-session - Select session
@router.post("/select-session")
async def select_session(body: Dict[str, str]):
    """
    Select session.
    
    Navigate the TUI to display the specified session.
    """
    try:
        from session import get_session
        
        session_id = body.get("session_id")
        if not session_id:
            raise ValueError("session_id is required")
        
        # Verify session exists
        await get_session(session_id)
        
        await Bus.publish(SessionSelectEvent, {"session_id": session_id})
        return True
    except Exception as e:
        logger.error(f"Error selecting session: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Session not found")
        raise HTTPException(status_code=400, detail=str(e))


# TUI Control routes
control_router = APIRouter()


# GET /tui/control/next - Get next TUI request
@control_router.get("/next")
async def get_next_request():
    """
    Get next TUI request.
    
    Retrieve the next TUI (Terminal User Interface) request from the queue for processing.
    """
    try:
        req = await _tui_request_queue.next()
        return req
    except Exception as e:
        logger.error(f"Error getting next request: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /tui/control/response - Submit TUI response
@control_router.post("/response")
async def submit_response(body: Any):
    """
    Submit TUI response.
    
    Submit a response to the TUI request queue to complete a pending request.
    """
    try:
        await _tui_response_queue.push(body)
        return True
    except Exception as e:
        logger.error(f"Error submitting response: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Include control routes
router.include_router(control_router, prefix="/control")


# Helper function for TUI calls
async def call_tui(path: str, body: Dict[str, Any]) -> Any:
    """
    Call TUI with a request and wait for response.
    
    Args:
        path: Request path
        body: Request body
    
    Returns:
        Response from TUI
    """
    await _tui_request_queue.push({
        "path": path,
        "body": body,
    })
    return await _tui_response_queue.next()
