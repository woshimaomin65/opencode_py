"""
Tool module for OpenCode.

Handles tool definitions and execution including:
- Read
- Write
- Edit
- Shell
- Search
- Web
- LSP
- And custom tools
"""

import asyncio
import json
import os
import subprocess
import shutil
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, Callable, Union, List, Dict
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class ToolStatus(Enum):
    """Tool execution status."""
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""
    name: str
    type: str  # "string", "number", "boolean", "array", "object"
    description: str
    required: bool = False
    default: Any = None
    enum: Optional[list] = None


@dataclass
class ToolDefinition:
    """Definition of a tool."""
    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to JSON Schema format for LLM."""
        properties = {}
        required = []
        
        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
            
            properties[param.name] = prop
            
            if param.required:
                required.append(param.name)
        
        schema = {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
            },
        }
        
        if required:
            schema["inputSchema"]["required"] = required
        
        return schema


@dataclass
class ToolResult:
    """Result from tool execution."""
    tool_name: str
    status: ToolStatus
    content: Any
    error: Optional[str] = None
    title: Optional[str] = None
    metadata: Optional[dict] = None
    attachments: Optional[list] = None


class ToolContext:
    """Context for tool execution."""
    
    def __init__(
        self,
        session_id: str,
        message_id: str,
        agent: str,
        abort_signal: Optional[asyncio.Event] = None,
        call_id: Optional[str] = None,
        extra: Optional[dict] = None,
        messages: Optional[list] = None,
        working_dir: Optional[Path] = None,
    ):
        self.session_id = session_id
        self.message_id = message_id
        self.agent = agent
        self.abort_signal = abort_signal or asyncio.Event()
        self.call_id = call_id
        self.extra = extra or {}
        self.messages = messages or []
        self.working_dir = working_dir or Path.cwd()
        self._metadata_output = ""
        self._metadata_description = ""
    
    def metadata(self, input: dict) -> None:
        """Update metadata for the tool execution."""
        if "metadata" in input:
            meta = input["metadata"]
            if "output" in meta:
                self._metadata_output = meta["output"]
            if "description" in meta:
                self._metadata_description = meta["description"]
    
    async def ask(self, permission: str, patterns: list[str], always: list[str], metadata: dict) -> None:
        """Request permission for the tool operation."""
        # This would integrate with the permission system
        # For now, just log the request
        pass
    
    @property
    def aborted(self) -> bool:
        """Check if the operation was aborted."""
        return self.abort_signal.is_set()


class BaseTool(ABC):
    """Abstract base class for all tools."""
    
    @property
    @abstractmethod
    def definition(self) -> ToolDefinition:
        """Get the tool definition."""
        pass
    
    @abstractmethod
    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        """Execute the tool with given parameters and context."""
        pass
    
    def validate_params(self, **kwargs) -> tuple[bool, Optional[str]]:
        """Validate parameters against definition."""
        for param in self.definition.parameters:
            if param.required and param.name not in kwargs:
                return False, f"Missing required parameter: {param.name}"
            
            if param.name in kwargs:
                value = kwargs[param.name]
                # Basic type checking
                if param.type == "string" and not isinstance(value, str):
                    return False, f"Parameter {param.name} must be a string"
                elif param.type == "number" and not isinstance(value, (int, float)):
                    return False, f"Parameter {param.name} must be a number"
                elif param.type == "boolean" and not isinstance(value, bool):
                    return False, f"Parameter {param.name} must be a boolean"
                elif param.type == "array" and not isinstance(value, list):
                    return False, f"Parameter {param.name} must be an array"
                elif param.type == "object" and not isinstance(value, dict):
                    return False, f"Parameter {param.name} must be an object"
                
                # Enum validation
                if param.enum and value not in param.enum:
                    return False, f"Parameter {param.name} must be one of {param.enum}"
        
        return True, None


class ToolRegistry:
    """Registry for managing tools."""
    
    _tools: dict[str, BaseTool] = {}
    
    @classmethod
    def register(cls, tool: BaseTool) -> None:
        """Register a tool."""
        cls._tools[tool.definition.name] = tool
    
    @classmethod
    def get(cls, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return cls._tools.get(name)
    
    @classmethod
    def list_tools(cls) -> list[ToolDefinition]:
        """List all registered tools."""
        return [tool.definition for tool in cls._tools.values()]
    
    @classmethod
    async def execute(cls, name: str, ctx: ToolContext, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        tool = cls.get(name)
        if not tool:
            return ToolResult(
                tool_name=name,
                status=ToolStatus.ERROR,
                content=None,
                error=f"Unknown tool: {name}",
            )
        return await tool.execute(ctx, **kwargs)


# Initialize default tools
def init_default_tools(working_dir: Optional[Path] = None) -> None:
    """Initialize default tools."""
    from .read import ReadTool
    from .write import WriteTool
    from .edit import EditTool
    from .bash import BashTool
    from .search import SearchTool
    
    ToolRegistry.register(ReadTool())
    ToolRegistry.register(WriteTool())
    ToolRegistry.register(EditTool())
    from .bash import BashToolConfig
    ToolRegistry.register(BashTool(BashToolConfig(working_dir=Path(working_dir) if working_dir else None)))
    ToolRegistry.register(SearchTool())
