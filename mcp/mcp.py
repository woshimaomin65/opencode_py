"""
MCP (Model Context Protocol) module for OpenCode.

Handles MCP server integration for connecting to external tools and services.
Reference: https://modelcontextprotocol.io/
"""

import json
import asyncio
from typing import Any, Optional, AsyncIterator
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum


class MCPServerStatus(Enum):
    """MCP server status."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    working_dir: Optional[Path] = None
    timeout: int = 30  # Connection timeout in seconds


@dataclass
class MCPTool:
    """A tool provided by an MCP server."""
    name: str
    description: str
    input_schema: dict
    server_name: str


@dataclass
class MCPResource:
    """A resource provided by an MCP server."""
    uri: str
    name: str
    description: str
    mime_type: str
    server_name: str


class MCPServer:
    """
    MCP Server connection.
    
    Connects to an MCP server via stdio and provides tools and resources.
    """
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.status = MCPServerStatus.STOPPED
        self._process: Optional[asyncio.subprocess.Process] = None
        self._message_id = 0
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._tools: list[MCPTool] = []
        self._resources: list[MCPResource] = []
        self._receive_task: Optional[asyncio.Task] = None
    
    async def start(self) -> bool:
        """Start the MCP server."""
        if self.status == MCPServerStatus.RUNNING:
            return True
        
        self.status = MCPServerStatus.STARTING
        
        try:
            # Start the server process
            self._process = await asyncio.create_subprocess_exec(
                self.config.command,
                *self.config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config.working_dir,
                env={**dict(Path.cwd().env()), **self.config.env},
            )
            
            # Start receiving messages
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            # Initialize connection
            await self._initialize()
            
            # List tools and resources
            await self._list_tools()
            await self._list_resources()
            
            self.status = MCPServerStatus.RUNNING
            return True
            
        except Exception as e:
            self.status = MCPServerStatus.ERROR
            print(f"Failed to start MCP server {self.config.name}: {e}")
            return False
    
    async def stop(self) -> None:
        """Stop the MCP server."""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
        
        self.status = MCPServerStatus.STOPPED
    
    async def _send_message(self, method: str, params: Optional[dict] = None) -> dict:
        """Send a JSON-RPC message."""
        self._message_id += 1
        message_id = self._message_id
        
        message = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": method,
        }
        
        if params:
            message["params"] = params
        
        # Send message
        message_bytes = (json.dumps(message) + "\n").encode('utf-8')
        self._process.stdin.write(message_bytes)
        await self._process.stdin.drain()
        
        # Wait for response
        future = asyncio.Future()
        self._pending_requests[message_id] = future
        
        try:
            response = await asyncio.wait_for(future, timeout=self.config.timeout)
            return response
        except asyncio.TimeoutError:
            raise TimeoutError(f"MCP request timeout: {method}")
        finally:
            self._pending_requests.pop(message_id, None)
    
    async def _receive_loop(self) -> None:
        """Receive and process messages from the server."""
        buffer = b""
        
        while self._process and self._process.returncode is None:
            try:
                # Read available data
                data = await self._process.stdout.read(4096)
                if not data:
                    break
                
                buffer += data
                
                # Process complete messages
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line:
                        await self._process_message(json.loads(line))
                        
            except Exception as e:
                print(f"MCP receive error: {e}")
                break
        
        self.status = MCPServerStatus.STOPPED
    
    async def _process_message(self, message: dict) -> None:
        """Process a received JSON-RPC message."""
        if "id" in message:
            # Response to a request
            message_id = message["id"]
            future = self._pending_requests.get(message_id)
            if future:
                if "error" in message:
                    future.set_exception(Exception(message["error"]["message"]))
                else:
                    future.set_result(message.get("result", {}))
        elif "method" in message:
            # Notification or request from server
            method = message["method"]
            params = message.get("params", {})
            
            if method == "notifications/tools/list_changed":
                # Tools changed, refresh
                await self._list_tools()
            elif method == "notifications/resources/list_changed":
                # Resources changed, refresh
                await self._list_resources()
    
    async def _initialize(self) -> None:
        """Initialize the MCP connection."""
        result = await self._send_message("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "opencode-py",
                "version": "0.1.0",
            },
        })
        
        # Send initialized notification
        await self._send_message("notifications/initialized")
    
    async def _list_tools(self) -> None:
        """List available tools from the server."""
        try:
            result = await self._send_message("tools/list")
            self._tools = []
            
            for tool_data in result.get("tools", []):
                self._tools.append(MCPTool(
                    name=tool_data["name"],
                    description=tool_data.get("description", ""),
                    input_schema=tool_data.get("inputSchema", {}),
                    server_name=self.config.name,
                ))
        except Exception as e:
            print(f"Failed to list MCP tools: {e}")
    
    async def _list_resources(self) -> None:
        """List available resources from the server."""
        try:
            result = await self._send_message("resources/list")
            self._resources = []
            
            for resource_data in result.get("resources", []):
                self._resources.append(MCPResource(
                    uri=resource_data["uri"],
                    name=resource_data.get("name", ""),
                    description=resource_data.get("description", ""),
                    mime_type=resource_data.get("mimeType", "text/plain"),
                    server_name=self.config.name,
                ))
        except Exception as e:
            print(f"Failed to list MCP resources: {e}")
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool on the MCP server."""
        result = await self._send_message("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        return result
    
    async def read_resource(self, uri: str) -> str:
        """Read a resource from the MCP server."""
        result = await self._send_message("resources/read", {
            "uri": uri,
        })
        
        contents = result.get("contents", [])
        if contents:
            return contents[0].get("text", "")
        return ""
    
    @property
    def tools(self) -> list[MCPTool]:
        """Get available tools."""
        return self._tools
    
    @property
    def resources(self) -> list[MCPResource]:
        """Get available resources."""
        return self._resources


class MCPManager:
    """
    Manager for MCP servers.
    
    Handles:
    - Starting and stopping servers
    - Tool discovery
    - Tool execution routing
    """
    
    def __init__(self):
        self._servers: dict[str, MCPServer] = {}
    
    def add_server(self, config: MCPServerConfig) -> None:
        """Add an MCP server configuration."""
        self._servers[config.name] = MCPServer(config)
    
    def remove_server(self, name: str) -> None:
        """Remove an MCP server."""
        if name in self._servers:
            del self._servers[name]
    
    async def start_server(self, name: str) -> bool:
        """Start an MCP server."""
        server = self._servers.get(name)
        if not server:
            print(f"MCP server not found: {name}")
            return False
        return await server.start()
    
    async def stop_server(self, name: str) -> None:
        """Stop an MCP server."""
        server = self._servers.get(name)
        if server:
            await server.stop()
    
    async def start_all(self) -> None:
        """Start all MCP servers."""
        for server in self._servers.values():
            await server.start()
    
    async def stop_all(self) -> None:
        """Stop all MCP servers."""
        for server in self._servers.values():
            await server.stop()
    
    def get_all_tools(self) -> list[MCPTool]:
        """Get all tools from all servers."""
        tools = []
        for server in self._servers.values():
            if server.status == MCPServerStatus.RUNNING:
                tools.extend(server.tools)
        return tools
    
    def get_server_for_tool(self, tool_name: str) -> Optional[MCPServer]:
        """Get the server that provides a specific tool."""
        for server in self._servers.values():
            for tool in server.tools:
                if tool.name == tool_name:
                    return server
        return None
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool on any server."""
        server = self.get_server_for_tool(tool_name)
        if not server:
            raise ValueError(f"Tool not found: {tool_name}")
        return await server.call_tool(tool_name, arguments)
