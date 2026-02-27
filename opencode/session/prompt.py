"""
Session Prompt module for OpenCode.

Handles session prompting including:
- Creating user messages
- Processing loop for agent responses
- Tool resolution and execution
- Structured output handling
"""

import asyncio
import os
from pathlib import Path
from typing import Any, Optional, AsyncIterator
from dataclasses import dataclass

from .manager import SessionManager, Database, NotFoundError
from .message_v2 import (
    MessageWithParts,
    UserMessage,
    AssistantMessage,
    TextPart,
    FilePart,
    AgentPart,
    SubtaskPart,
    filter_compacted,
)
from ..id import generate_id, generate_message_id, generate_part_id
from ..bus import Bus
from ..agent import Agent, get_agent
from ..provider import get_provider
from ..tool import ToolRegistry, ToolContext
from ..util import defer


# Structured output prompts
STRUCTURED_OUTPUT_DESCRIPTION = """Use this tool to return your final response in the requested structured format.

IMPORTANT:
- You MUST call this tool exactly once at the end of your response
- The input must be valid JSON matching the required schema
- Complete all necessary research and tool calls BEFORE calling this tool
- This tool provides your final answer - no further actions are taken after calling it"""

STRUCTURED_OUTPUT_SYSTEM_PROMPT = """IMPORTANT: The user has requested structured output. You MUST use the StructuredOutput tool to provide your final response. Do NOT respond with plain text - you MUST call the StructuredOutput tool with your answer formatted according to the schema."""


@dataclass
class PromptInput:
    """Input for session prompt."""
    session_id: str
    message_id: Optional[str] = None
    model: Optional[dict] = None
    agent: Optional[str] = None
    no_reply: bool = False
    tools: Optional[dict[str, bool]] = None
    format: Optional[dict] = None
    system: Optional[str] = None
    variant: Optional[str] = None
    parts: Optional[list[dict]] = None


@dataclass
class LoopInput:
    """Input for processing loop."""
    session_id: str
    resume_existing: bool = False


class SessionBusyError(Exception):
    """Raised when session is busy."""
    
    def __init__(self, session_id: str):
        super().__init__(f"Session {session_id} is busy")
        self.session_id = session_id


class SessionPrompt:
    """
    Session prompt handler.
    
    Manages the prompting loop for session-based interactions.
    """
    
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self._busy_sessions: dict[str, asyncio.Event] = {}
        self._callbacks: dict[str, list] = {}
    
    def assert_not_busy(self, session_id: str) -> None:
        """Assert that session is not busy."""
        if session_id in self._busy_sessions:
            raise SessionBusyError(session_id)
    
    async def prompt(self, input: PromptInput) -> MessageWithParts:
        """Process a prompt for a session."""
        session = self.session_manager.get(input.session_id)
        if not session:
            raise NotFoundError(f"Session not found: {input.session_id}")
        
        # Create user message
        message = await self._create_user_message(input)
        
        # Touch session
        self.session_manager.touch(input.session_id)
        
        # Handle permissions (deprecated tools parameter)
        if input.tools:
            permissions = []
            for tool, enabled in input.tools.items():
                permissions.append({
                    "permission": tool,
                    "action": "allow" if enabled else "deny",
                    "pattern": "*",
                })
            if permissions:
                session.permission = permissions
                self.session_manager.set_permission(input.session_id, permissions)
        
        if input.no_reply:
            return message
        
        # Process loop
        return await self.loop(LoopInput(
            session_id=input.session_id,
            resume_existing=False,
        ))
    
    async def _create_user_message(self, input: PromptInput) -> MessageWithParts:
        """Create a user message."""
        agent_name = input.agent or await get_default_agent()
        agent = await get_agent(agent_name)
        
        model = input.model
        if not model:
            model = agent.model if agent and agent.model else await get_default_model()
        
        # Create message info
        info = {
            "id": input.message_id or generate_message_id(),
            "role": "user",
            "sessionID": input.session_id,
            "time": {"created": int(asyncio.get_event_loop().time() * 1000)},
            "tools": input.tools,
            "agent": agent_name,
            "model": model,
            "system": input.system,
            "format": input.format,
            "variant": input.variant,
        }
        
        # Process parts
        parts = []
        if input.parts:
            for part in input.parts:
                processed = await self._process_part(part, info, input.session_id)
                parts.extend(processed)
        
        # Update message in database
        self.session_manager.update_message(info)
        for part in parts:
            self.session_manager.update_part(part)
        
        return MessageWithParts(info=info, parts=parts)
    
    async def _process_part(self, part: dict, message_info: dict, session_id: str) -> list[dict]:
        """Process a single part."""
        part_id = part.get("id") or generate_part_id()
        
        if part["type"] == "file":
            # Handle file parts
            url = part.get("url", "")
            if url.startswith("data:"):
                if part.get("mime") == "text/plain":
                    # Inline text file
                    import base64
                    data = url.split(",", 1)[1] if "," in url else url
                    text = base64.b64decode(data).decode("utf-8")
                    
                    return [
                        {
                            "id": generate_part_id(),
                            "messageID": message_info["id"],
                            "sessionID": session_id,
                            "type": "text",
                            "synthetic": True,
                            "text": f"Called the Read tool with the following input: {{\"filePath\": {part.get('filename')}}}",
                        },
                        {
                            "id": generate_part_id(),
                            "messageID": message_info["id"],
                            "sessionID": session_id,
                            "type": "text",
                            "synthetic": True,
                            "text": text,
                        },
                        {
                            "id": part_id,
                            "messageID": message_info["id"],
                            "sessionID": session_id,
                            "type": "file",
                            **part,
                        },
                    ]
            
            elif url.startswith("file:"):
                # Local file
                from urllib.parse import unquote, urlparse
                filepath = unquote(urlparse(url).path)
                
                if part.get("mime") == "text/plain":
                    # Read text file
                    try:
                        with open(filepath, "r") as f:
                            content = f.read()
                        
                        return [
                            {
                                "id": generate_part_id(),
                                "messageID": message_info["id"],
                                "sessionID": session_id,
                                "type": "text",
                                "synthetic": True,
                                "text": f'Called the Read tool with the following input: {{"filePath":"{filepath}"}}',
                            },
                            {
                                "id": generate_part_id(),
                                "messageID": message_info["id"],
                                "sessionID": session_id,
                                "type": "text",
                                "synthetic": True,
                                "text": content,
                            },
                            {
                                "id": part_id,
                                "messageID": message_info["id"],
                                "sessionID": session_id,
                                "type": "file",
                                **part,
                            },
                        ]
                    except Exception as e:
                        return [
                            {
                                "id": generate_part_id(),
                                "messageID": message_info["id"],
                                "sessionID": session_id,
                                "type": "text",
                                "synthetic": True,
                                "text": f"Read tool failed to read {filepath}: {str(e)}",
                            },
                        ]
                else:
                    # Binary file
                    import base64
                    try:
                        with open(filepath, "rb") as f:
                            content = base64.b64encode(f.read()).decode("utf-8")
                        
                        return [
                            {
                                "id": generate_part_id(),
                                "messageID": message_info["id"],
                                "sessionID": session_id,
                                "type": "text",
                                "synthetic": True,
                                "text": f'Called the Read tool with the following input: {{"filePath":"{filepath}"}}',
                            },
                            {
                                "id": part_id,
                                "messageID": message_info["id"],
                                "sessionID": session_id,
                                "type": "file",
                                "url": f"data:{part.get('mime')};base64,{content}",
                                "mime": part.get("mime"),
                                "filename": part.get("filename"),
                            },
                        ]
                    except Exception as e:
                        return [
                            {
                                "id": generate_part_id(),
                                "messageID": message_info["id"],
                                "sessionID": session_id,
                                "type": "text",
                                "synthetic": True,
                                "text": f"Failed to read file {filepath}: {str(e)}",
                            },
                        ]
        
        elif part["type"] == "agent":
            # Agent invocation
            return [
                {
                    "id": part_id,
                    "messageID": message_info["id"],
                    "sessionID": session_id,
                    "type": "agent",
                    "name": part["name"],
                },
                {
                    "id": generate_part_id(),
                    "messageID": message_info["id"],
                    "sessionID": session_id,
                    "type": "text",
                    "synthetic": True,
                    "text": f" Use the above message and context to generate a prompt and call the task tool with subagent: {part['name']}",
                },
            ]
        
        # Default: return part as-is
        return [
            {
                "id": part_id,
                "messageID": message_info["id"],
                "sessionID": session_id,
                **part,
            },
        ]
    
    async def loop(self, input: LoopInput) -> MessageWithParts:
        """Process the conversation loop."""
        session_id = input.session_id
        
        # Start busy tracking
        abort_event = asyncio.Event()
        self._busy_sessions[session_id] = abort_event
        self._callbacks[session_id] = []
        
        try:
            step = 0
            max_steps = 50  # Default max iterations
            
            while step < max_steps:
                if abort_event.is_set():
                    break
                
                step += 1
                
                # Get messages
                messages = self.session_manager.list_messages(session_id)
                messages_with_parts = [
                    MessageWithParts(info=m["info"], parts=m["parts"])
                    for m in messages
                ]
                messages_with_parts = filter_compacted(messages_with_parts)
                
                # Find last user and assistant messages
                last_user = None
                last_assistant = None
                
                for msg in reversed(messages_with_parts):
                    if msg.info.role == "user" and last_user is None:
                        last_user = msg.info
                    if msg.info.role == "assistant" and last_assistant is None:
                        last_assistant = msg.info
                    if last_user and last_assistant:
                        break
                
                if not last_user:
                    raise Exception("No user message found in stream")
                
                # Check if finished
                if (
                    last_assistant
                    and getattr(last_assistant, "finish", None)
                    and getattr(last_assistant, "finish", None) not in ["tool-calls", "unknown"]
                ):
                    break
                
                # Get model
                model_info = getattr(last_user, "model", {})
                provider_id = model_info.get("providerID", "anthropic")
                model_id = model_info.get("modelID", "claude-sonnet-4-20250514")
                
                provider = get_provider(provider_id, model_id)
                
                # Get agent
                agent_name = getattr(last_user, "agent", "build")
                agent = await get_agent(agent_name)
                
                # Create assistant message
                assistant_info = {
                    "id": generate_message_id(),
                    "parentID": last_user.id,
                    "role": "assistant",
                    "mode": agent_name,
                    "agent": agent_name,
                    "variant": getattr(last_user, "variant", None),
                    "path": {"cwd": os.getcwd(), "root": os.getcwd()},
                    "cost": 0,
                    "tokens": {
                        "input": 0,
                        "output": 0,
                        "reasoning": 0,
                        "cache": {"read": 0, "write": 0},
                    },
                    "modelID": model_id,
                    "providerID": provider_id,
                    "time": {"created": int(asyncio.get_event_loop().time() * 1000)},
                    "sessionID": session_id,
                }
                
                self.session_manager.update_message(assistant_info)
                
                # Convert messages for provider
                model_messages = []
                for msg in messages_with_parts:
                    if msg.info.role == "user":
                        content = []
                        for part in msg.parts:
                            if part.type == "text" and not getattr(part, "ignored", False):
                                content.append({"type": "text", "text": part.text})
                        if content:
                            model_messages.append({"role": "user", "content": content})
                    
                    elif msg.info.role == "assistant":
                        content = []
                        for part in msg.parts:
                            if part.type == "text":
                                content.append({"type": "text", "text": part.text})
                        if content:
                            model_messages.append({"role": "assistant", "content": content})
                
                # Get tools
                tools = await self._resolve_tools(agent, session_id, assistant_info["id"])
                
                # Call provider
                response = await provider.complete(
                    messages=model_messages,
                    tools=tools if tools else None,
                    temperature=agent.temperature if agent else 0.7,
                )
                
                # Add assistant text
                if response.content:
                    self.session_manager.update_part({
                        "id": generate_part_id(),
                        "messageID": assistant_info["id"],
                        "sessionID": session_id,
                        "type": "text",
                        "text": response.content,
                    })
                
                # Handle tool calls
                if response.tool_calls:
                    assistant_info["finish"] = "tool-calls"
                    assistant_info["time"]["completed"] = int(asyncio.get_event_loop().time() * 1000)
                    self.session_manager.update_message(assistant_info)
                    
                    for tool_call in response.tool_calls:
                        # Create tool part
                        tool_part = {
                            "id": generate_part_id(),
                            "messageID": assistant_info["id"],
                            "sessionID": session_id,
                            "type": "tool",
                            "callID": tool_call.id,
                            "tool": tool_call.name,
                            "state": {
                                "status": "running",
                                "input": tool_call.arguments,
                                "time": {"start": int(asyncio.get_event_loop().time() * 1000)},
                            },
                        }
                        self.session_manager.update_part(tool_part)
                        
                        # Execute tool
                        try:
                            result = await ToolRegistry.execute(
                                tool_call.name,
                                **tool_call.arguments,
                            )
                            
                            # Update tool part with result
                            tool_part["state"] = {
                                "status": "completed",
                                "input": tool_call.arguments,
                                "output": result.content,
                                "title": result.title if hasattr(result, "title") else tool_call.name,
                                "metadata": {},
                                "time": {
                                    "start": tool_part["state"]["time"]["start"],
                                    "end": int(asyncio.get_event_loop().time() * 1000),
                                },
                            }
                            self.session_manager.update_part(tool_part)
                            
                            # Add tool result message
                            self.session_manager.update_message({
                                "id": generate_message_id(),
                                "role": "user",
                                "sessionID": session_id,
                                "time": {"created": int(asyncio.get_event_loop().time() * 1000)},
                                "agent": agent_name,
                                "model": model_info,
                            })
                            
                            self.session_manager.update_part({
                                "id": generate_part_id(),
                                "messageID": self.session_manager.list_messages(session_id)[-1]["info"]["id"],
                                "sessionID": session_id,
                                "type": "text",
                                "text": f"Tool {tool_call.name} result: {result.content}",
                            })
                            
                        except Exception as e:
                            tool_part["state"] = {
                                "status": "error",
                                "input": tool_call.arguments,
                                "error": str(e),
                                "time": {
                                    "start": tool_part["state"]["time"]["start"],
                                    "end": int(asyncio.get_event_loop().time() * 1000),
                                },
                            }
                            self.session_manager.update_part(tool_part)
                else:
                    # No tool calls, finish
                    assistant_info["finish"] = "stop"
                    assistant_info["time"]["completed"] = int(asyncio.get_event_loop().time() * 1000)
                    assistant_info["tokens"] = response.usage
                    self.session_manager.update_message(assistant_info)
                    
                    # Return final message
                    messages = self.session_manager.list_messages(session_id)
                    for msg in messages:
                        if msg["info"]["role"] == "assistant" and msg["info"]["id"] == assistant_info["id"]:
                            return MessageWithParts(info=msg["info"], parts=msg["parts"])
            
            # Max steps reached
            raise Exception("Max iterations reached")
            
        finally:
            # Clean up
            if session_id in self._busy_sessions:
                del self._busy_sessions[session_id]
            if session_id in self._callbacks:
                del self._callbacks[session_id]
    
    async def _resolve_tools(self, agent, session_id: str, message_id: str) -> Optional[list[dict]]:
        """Resolve available tools."""
        if not agent:
            return None
        
        tools = []
        # Get tools from registry
        for tool_name in agent.tools if hasattr(agent, "tools") else []:
            tool = ToolRegistry.get(tool_name)
            if tool:
                tools.append(tool.definition)
        
        return tools if tools else None
    
    def cancel(self, session_id: str) -> None:
        """Cancel a running prompt."""
        if session_id in self._busy_sessions:
            self._busy_sessions[session_id].set()


async def get_default_agent() -> str:
    """Get default agent name."""
    return "build"


async def get_default_model() -> dict:
    """Get default model info."""
    return {
        "providerID": "anthropic",
        "modelID": "claude-sonnet-4-20250514",
    }


# Module-level convenience
_session_prompt: Optional[SessionPrompt] = None


def get_session_prompt(session_manager: SessionManager) -> SessionPrompt:
    """Get or create session prompt handler."""
    global _session_prompt
    if _session_prompt is None:
        _session_prompt = SessionPrompt(session_manager)
    return _session_prompt


async def prompt(
    session_manager: SessionManager,
    session_id: str,
    parts: list[dict],
    agent: Optional[str] = None,
    model: Optional[dict] = None,
    no_reply: bool = False,
) -> MessageWithParts:
    """Convenience function to prompt a session."""
    handler = get_session_prompt(session_manager)
    return await handler.prompt(PromptInput(
        session_id=session_id,
        parts=parts,
        agent=agent,
        model=model,
        no_reply=no_reply,
    ))
