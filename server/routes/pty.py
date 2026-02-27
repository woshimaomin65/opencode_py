"""
PTY (Pseudo-Terminal) routes for OpenCode server.

Provides API endpoints for PTY session management:
- List, create, get, update, remove PTY sessions
- WebSocket connection for PTY interaction
"""

import logging
import asyncio
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, HTTPException, Path, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pty", tags=["pty"])


# Placeholder for PTY module
class PtySession:
    """PTY session representation."""
    
    def __init__(self, session_id: str, command: str, cwd: str = "."):
        self.id = session_id
        self.command = command
        self.cwd = cwd
        self.status = "running"
        self.created_at = asyncio.get_event_loop().time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "command": self.command,
            "cwd": self.cwd,
            "status": self.status,
            "created_at": self.created_at,
        }


class PtyManager:
    """Manager for PTY sessions."""
    
    def __init__(self):
        self._sessions: Dict[str, PtySession] = {}
        self._connections: Dict[str, List[Any]] = {}
    
    def list(self) -> List[Dict[str, Any]]:
        """List all PTY sessions."""
        return [session.to_dict() for session in self._sessions.values()]
    
    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a PTY session."""
        session = self._sessions.get(session_id)
        return session.to_dict() if session else None
    
    async def create(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new PTY session."""
        import uuid
        
        session_id = body.get("id", str(uuid.uuid4()))
        command = body.get("command", "bash")
        cwd = body.get("cwd", ".")
        
        session = PtySession(session_id, command, cwd)
        self._sessions[session_id] = session
        self._connections[session_id] = []
        
        return session.to_dict()
    
    async def update(self, session_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """Update a PTY session."""
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self._sessions[session_id]
        
        # Update allowed fields
        if "status" in body:
            session.status = body["status"]
        
        return session.to_dict()
    
    async def remove(self, session_id: str) -> None:
        """Remove a PTY session."""
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")
        
        # Close all connections
        for connection in self._connections.get(session_id, []):
            try:
                await connection.close()
            except:
                pass
        
        del self._sessions[session_id]
        del self._connections[session_id]
    
    def connect(self, session_id: str, websocket: Any, cursor: Optional[int] = None) -> 'PtyConnection':
        """Connect to a PTY session via WebSocket."""
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")
        
        connection = PtyConnection(self, session_id, websocket, cursor)
        self._connections[session_id].append(websocket)
        return connection


# Global PTY manager instance
_pty_manager = PtyManager()


def get_pty_manager() -> PtyManager:
    """Get the PTY manager instance."""
    return _pty_manager


class PtyConnection:
    """PTY WebSocket connection handler."""
    
    def __init__(self, manager: PtyManager, session_id: str, websocket: Any, cursor: Optional[int] = None):
        self.manager = manager
        self.session_id = session_id
        self.websocket = websocket
        self.cursor = cursor
        self.running = True
    
    async def on_message(self, data: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            # Parse message and send to PTY
            import json
            message = json.loads(data)
            
            # Handle different message types
            msg_type = message.get("type")
            
            if msg_type == "input":
                # Send input to PTY process
                await self._send_input(message.get("data", ""))
            elif msg_type == "resize":
                # Handle terminal resize
                await self._resize(message.get("cols"), message.get("rows"))
            elif msg_type == "ping":
                # Respond to ping
                await self.websocket.send_json({"type": "pong"})
        except Exception as e:
            logger.error(f"Error handling PTY message: {e}")
    
    async def _send_input(self, data: str) -> None:
        """Send input to PTY process."""
        # Implementation depends on PTY backend
        session = self.manager._sessions.get(self.session_id)
        if session:
            # In a real implementation, this would write to the PTY
            logger.debug(f"Sending input to PTY {self.session_id}: {data[:50]}...")
    
    async def _resize(self, cols: int, rows: int) -> None:
        """Resize PTY terminal."""
        # Implementation depends on PTY backend
        logger.debug(f"Resizing PTY {self.session_id} to {cols}x{rows}")
    
    async def on_close(self) -> None:
        """Handle WebSocket close."""
        self.running = False
        # Remove from connections list
        if self.websocket in self.manager._connections.get(self.session_id, []):
            self.manager._connections[self.session_id].remove(self.websocket)


# GET /pty/ - List PTY sessions
@router.get("/")
async def list_pty_sessions():
    """
    List PTY sessions.
    
    Get a list of all active pseudo-terminal (PTY) sessions managed by OpenCode.
    """
    try:
        manager = get_pty_manager()
        return manager.list()
    except Exception as e:
        logger.error(f"Error listing PTY sessions: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# POST /pty/ - Create PTY session
@router.post("/")
async def create_pty_session(body: Dict[str, Any]):
    """
    Create PTY session.
    
    Create a new pseudo-terminal (PTY) session for running shell commands and processes.
    """
    try:
        manager = get_pty_manager()
        info = await manager.create(body)
        return info
    except Exception as e:
        logger.error(f"Error creating PTY session: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# GET /pty/{ptyID} - Get PTY session
@router.get("/{pty_id}")
async def get_pty_session(pty_id: str = Path(..., description="PTY session ID")):
    """
    Get PTY session.
    
    Retrieve detailed information about a specific pseudo-terminal (PTY) session.
    """
    try:
        manager = get_pty_manager()
        info = manager.get(pty_id)
        if not info:
            raise HTTPException(status_code=404, detail="PTY session not found")
        return info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting PTY session {pty_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# PUT /pty/{ptyID} - Update PTY session
@router.put("/{pty_id}")
async def update_pty_session(
    pty_id: str = Path(..., description="PTY session ID"),
    body: Dict[str, Any] = None,
):
    """
    Update PTY session.
    
    Update properties of an existing pseudo-terminal (PTY) session.
    """
    try:
        body = body or {}
        manager = get_pty_manager()
        info = await manager.update(pty_id, body)
        return info
    except Exception as e:
        logger.error(f"Error updating PTY session {pty_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="PTY session not found")
        raise HTTPException(status_code=400, detail=str(e))


# DELETE /pty/{ptyID} - Remove PTY session
@router.delete("/{pty_id}")
async def remove_pty_session(pty_id: str = Path(..., description="PTY session ID")):
    """
    Remove PTY session.
    
    Remove and terminate a specific pseudo-terminal (PTY) session.
    """
    try:
        manager = get_pty_manager()
        await manager.remove(pty_id)
        return True
    except Exception as e:
        logger.error(f"Error removing PTY session {pty_id}: {e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="PTY session not found")
        raise HTTPException(status_code=400, detail=str(e))


# WebSocket /pty/{ptyID}/connect - Connect to PTY session
@router.websocket("/{pty_id}/connect")
async def connect_pty_session(
    websocket: WebSocket,
    pty_id: str = Path(..., description="PTY session ID"),
    cursor: Optional[int] = Query(None, description="Output cursor position"),
):
    """
    Connect to PTY session.
    
    Establish a WebSocket connection to interact with a pseudo-terminal (PTY) session in real-time.
    """
    try:
        await websocket.accept()
        
        manager = get_pty_manager()
        
        # Check if session exists
        if not manager.get(pty_id):
            await websocket.close(code=4004, reason="Session not found")
            return
        
        # Create connection handler
        connection = manager.connect(pty_id, websocket, cursor)
        
        try:
            while connection.running:
                # Receive message
                data = await websocket.receive_text()
                await connection.on_message(data)
        except WebSocketDisconnect:
            logger.info(f"PTY WebSocket disconnected: {pty_id}")
        finally:
            await connection.on_close()
    
    except Exception as e:
        logger.error(f"Error in PTY WebSocket connection {pty_id}: {e}")
        try:
            await websocket.close(code=4000, reason=str(e))
        except:
            pass
