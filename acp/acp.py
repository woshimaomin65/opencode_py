"""
ACP (Agent Communication Protocol) module for OpenCode.

Handles agent-to-agent communication including:
- Session management
- Message routing
- Agent discovery
"""

import asyncio
import json
from typing import Any, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class MessageType(Enum):
    """Type of ACP message."""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"


class AgentStatus(Enum):
    """Agent status."""
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"


@dataclass
class ACPMessage:
    """ACP message structure."""
    id: str
    type: MessageType
    sender: str
    recipient: str
    method: str
    params: dict = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "sender": self.sender,
            "recipient": self.recipient,
            "method": self.method,
            "params": self.params,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ACPMessage":
        return cls(
            id=data["id"],
            type=MessageType(data["type"]),
            sender=data["sender"],
            recipient=data["recipient"],
            method=data["method"],
            params=data.get("params", {}),
            result=data.get("result"),
            error=data.get("error"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
        )


@dataclass
class AgentInfo:
    """Information about an agent."""
    id: str
    name: str
    status: AgentStatus
    capabilities: list[str] = field(default_factory=list)
    endpoint: Optional[str] = None
    last_seen: Optional[datetime] = None


class ACPTransport:
    """Base transport for ACP communication."""
    
    async def send(self, message: ACPMessage) -> None:
        """Send a message."""
        raise NotImplementedError
    
    async def receive(self) -> ACPMessage:
        """Receive a message."""
        raise NotImplementedError
    
    async def close(self) -> None:
        """Close the transport."""
        pass


class StdioTransport(ACPTransport):
    """Stdio-based transport for ACP."""
    
    def __init__(self):
        self._queue: asyncio.Queue[ACPMessage] = asyncio.Queue()
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start receiving messages."""
        self._running = True
        self._task = asyncio.create_task(self._receive_loop())
    
    async def _receive_loop(self) -> None:
        """Receive messages from stdin."""
        import sys
        
        while self._running:
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: sys.stdin.readline()
                )
                
                if not line:
                    break
                
                message = ACPMessage.from_dict(json.loads(line))
                await self._queue.put(message)
                
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error parsing message: {e}", file=sys.stderr)
    
    async def send(self, message: ACPMessage) -> None:
        """Send a message to stdout."""
        import sys
        
        line = json.dumps(message.to_dict()) + "\n"
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: sys.stdout.write(line) or sys.stdout.flush()
        )
    
    async def receive(self) -> ACPMessage:
        """Receive a message from queue."""
        return await self._queue.get()
    
    async def close(self) -> None:
        """Close the transport."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


class ACPServer:
    """
    ACP server for handling agent communication.
    """
    
    def __init__(self, agent_id: str, agent_name: str):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self._transport: Optional[ACPTransport] = None
        self._handlers: dict[str, Callable] = {}
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._agents: dict[str, AgentInfo] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    def set_transport(self, transport: ACPTransport) -> None:
        """Set the transport."""
        self._transport = transport
    
    def register_handler(self, method: str, handler: Callable) -> None:
        """Register a message handler."""
        self._handlers[method] = handler
    
    async def start(self) -> None:
        """Start the ACP server."""
        if not self._transport:
            raise RuntimeError("Transport not set")
        
        self._running = True
        self._task = asyncio.create_task(self._message_loop())
    
    async def stop(self) -> None:
        """Stop the ACP server."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        if self._transport:
            await self._transport.close()
    
    async def _message_loop(self) -> None:
        """Main message processing loop."""
        while self._running:
            try:
                message = await self._transport.receive()
                
                if message.type == MessageType.REQUEST:
                    await self._handle_request(message)
                elif message.type == MessageType.RESPONSE:
                    await self._handle_response(message)
                elif message.type == MessageType.NOTIFICATION:
                    await self._handle_notification(message)
                    
            except Exception as e:
                print(f"Error in message loop: {e}")
    
    async def _handle_request(self, message: ACPMessage) -> None:
        """Handle incoming request."""
        handler = self._handlers.get(message.method)
        
        if handler:
            try:
                result = await handler(message.params)
                response = ACPMessage(
                    id=message.id,
                    type=MessageType.RESPONSE,
                    sender=self.agent_id,
                    recipient=message.sender,
                    method=message.method,
                    result=result,
                )
                await self._transport.send(response)
            except Exception as e:
                error_response = ACPMessage(
                    id=message.id,
                    type=MessageType.ERROR,
                    sender=self.agent_id,
                    recipient=message.sender,
                    method=message.method,
                    error=str(e),
                )
                await self._transport.send(error_response)
        else:
            error_response = ACPMessage(
                id=message.id,
                type=MessageType.ERROR,
                sender=self.agent_id,
                recipient=message.sender,
                method=message.method,
                error=f"Unknown method: {message.method}",
            )
            await self._transport.send(error_response)
    
    async def _handle_response(self, message: ACPMessage) -> None:
        """Handle incoming response."""
        future = self._pending_requests.pop(message.id, None)
        if future:
            if message.error:
                future.set_exception(Exception(message.error))
            else:
                future.set_result(message.result)
    
    async def _handle_notification(self, message: ACPMessage) -> None:
        """Handle incoming notification."""
        # Notifications don't require response
        pass
    
    async def send_request(
        self,
        recipient: str,
        method: str,
        params: Optional[dict] = None,
        timeout: float = 30.0,
    ) -> Any:
        """
        Send a request and wait for response.
        
        Args:
            recipient: Target agent ID
            method: Method name
            params: Method parameters
            timeout: Request timeout
            
        Returns:
            Response result
        """
        from id import generate_id
        
        message = ACPMessage(
            id=generate_id("req"),
            type=MessageType.REQUEST,
            sender=self.agent_id,
            recipient=recipient,
            method=method,
            params=params or {},
        )
        
        future: asyncio.Future = asyncio.Future()
        self._pending_requests[message.id] = future
        
        await self._transport.send(message)
        
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_requests.pop(message.id, None)
            raise TimeoutError(f"Request to {recipient} timed out")
    
    async def send_notification(
        self,
        recipient: str,
        method: str,
        params: Optional[dict] = None,
    ) -> None:
        """
        Send a notification (no response expected).
        
        Args:
            recipient: Target agent ID
            method: Method name
            params: Method parameters
        """
        from id import generate_id
        
        message = ACPMessage(
            id=generate_id("notif"),
            type=MessageType.NOTIFICATION,
            sender=self.agent_id,
            recipient=recipient,
            method=method,
            params=params or {},
        )
        
        await self._transport.send(message)
    
    def register_agent(self, agent_info: AgentInfo) -> None:
        """Register an agent."""
        self._agents[agent_info.id] = agent_info
    
    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent."""
        self._agents.pop(agent_id, None)
    
    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent info."""
        return self._agents.get(agent_id)
    
    def list_agents(self) -> list[AgentInfo]:
        """List all registered agents."""
        return list(self._agents.values())


class ACPClient:
    """
    ACP client for connecting to ACP servers.
    """
    
    def __init__(self, client_id: str, client_name: str):
        self.client_id = client_id
        self.client_name = client_name
        self._transport: Optional[ACPTransport] = None
    
    async def connect(self, transport: ACPTransport) -> None:
        """Connect to an ACP server."""
        self._transport = transport
        await transport.start()
    
    async def disconnect(self) -> None:
        """Disconnect from ACP server."""
        if self._transport:
            await self._transport.close()
            self._transport = None
    
    async def send_request(
        self,
        method: str,
        params: Optional[dict] = None,
        timeout: float = 30.0,
    ) -> Any:
        """
        Send a request to the server.
        
        Args:
            method: Method name
            params: Method parameters
            timeout: Request timeout
            
        Returns:
            Response result
        """
        from id import generate_id
        
        message = ACPMessage(
            id=generate_id("req"),
            type=MessageType.REQUEST,
            sender=self.client_id,
            recipient="server",
            method=method,
            params=params or {},
        )
        
        future: asyncio.Future = asyncio.Future()
        
        def set_response(msg):
            if not future.done():
                if msg.error:
                    future.set_exception(Exception(msg.error))
                else:
                    future.set_result(msg.result)
        
        # Simple request/response without proper tracking
        await self._transport.send(message)
        
        try:
            response = await asyncio.wait_for(self._transport.receive(), timeout=timeout)
            if response.error:
                raise Exception(response.error)
            return response.result
        except asyncio.TimeoutError:
            raise TimeoutError("Request timed out")
