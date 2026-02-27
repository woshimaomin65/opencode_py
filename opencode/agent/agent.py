"""
Agent module for OpenCode.

Handles AI agent execution including:
- Agent configuration
- Tool integration
- Conversation loop
- Permission handling
- Multiple agent types (build, plan, explore, etc.)
"""

import asyncio
import os
from typing import Any, Optional, AsyncIterator, Callable
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel

from ..provider import (
    BaseProvider,
    ProviderRegistry,
    Message as ProviderMessage,
    ToolCall,
    get_provider,
)
from ..tool import (
    ToolRegistry,
    ToolResult,
    ToolStatus,
    ToolDefinition,
    ToolContext,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..session import Session
from ..permission import PermissionRule


class AgentMode(str, Enum):
    """Agent mode enum."""
    SUBAGENT = "subagent"
    PRIMARY = "primary"
    ALL = "all"


class AgentInfo(BaseModel):
    """Agent information model."""
    name: str
    description: Optional[str] = None
    mode: AgentMode = AgentMode.ALL
    native: bool = False
    hidden: bool = False
    top_p: Optional[float] = None
    temperature: Optional[float] = None
    color: Optional[str] = None
    permission: list[PermissionRule] = field(default_factory=list)
    model: Optional[dict] = None
    variant: Optional[str] = None
    prompt: Optional[str] = None
    options: dict = field(default_factory=dict)
    steps: Optional[int] = None


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str
    model: str
    provider: str = "anthropic"
    system_prompt: Optional[str] = None
    tools: list[str] = field(default_factory=list)
    max_iterations: int = 50
    temperature: float = 0.7
    options: dict = field(default_factory=dict)


@dataclass
class AgentStep:
    """A step in agent execution."""
    iteration: int
    user_message: Optional[str] = None
    assistant_message: Optional[str] = None
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    token_usage: dict = field(default_factory=dict)


class Agent:
    """
    AI Agent that can use tools to accomplish tasks.
    
    The agent runs a loop:
    1. Send current conversation to LLM
    2. If LLM returns tool calls, execute them
    3. Add tool results to conversation
    4. Repeat until no more tool calls or max iterations reached
    """
    
    def __init__(
        self,
        config: AgentConfig,
        working_dir: Optional[Path] = None,
        on_tool_call: Optional[Callable[[str, dict], None]] = None,
        on_tool_result: Optional[Callable[[str, ToolResult], None]] = None,
        on_message: Optional[Callable[[str, str], None]] = None,
    ):
        self.config = config
        self.working_dir = working_dir or Path.cwd()
        self.on_tool_call = on_tool_call
        self.on_tool_result = on_tool_result
        self.on_message = on_message
        
        # Initialize provider
        self.provider = get_provider(
            provider_type=config.provider,
            model=config.model,
        )
        
        # Get enabled tools
        self.tools: list[ToolDefinition] = []
        for tool_name in config.tools:
            tool = ToolRegistry.get(tool_name)
            if tool:
                self.tools.append(tool.definition)
            else:
                print(f"Warning: Tool '{tool_name}' not found")
        
        # Create session
        # Delayed import to avoid circular dependency
        from ..session import Session
        self.session = Session.create(
            model=config.model,
            provider=config.provider,
        )
        
        # Set system prompt
        if config.system_prompt:
            self.session.add_message("system", config.system_prompt)
        
        self._steps: list[AgentStep] = []
        self._current_iteration = 0
    
    @classmethod
    def create(
        cls,
        name: str = "default",
        model: str = "claude-sonnet-4-20250514",
        provider: str = "anthropic",
        system_prompt: Optional[str] = None,
        tools: Optional[list[str]] = None,
        max_iterations: int = 50,
        temperature: float = 0.7,
        working_dir: Optional[Path] = None,
        **kwargs,
    ) -> "Agent":
        """Create a new agent."""
        config = AgentConfig(
            name=name,
            model=model,
            provider=provider,
            system_prompt=system_prompt,
            tools=tools or [],
            max_iterations=max_iterations,
            temperature=temperature,
            options=kwargs,
        )
        return cls(config=config, working_dir=working_dir)
    
    async def run(self, user_message: str) -> str:
        """
        Run the agent with a user message.
        
        Returns the final response from the agent.
        """
        # Add user message to session
        self.session.add_message("user", user_message)
        
        if self.on_message:
            self.on_message("user", user_message)
        
        self._current_iteration = 0
        
        while self._current_iteration < self.config.max_iterations:
            self._current_iteration += 1
            
            step = AgentStep(iteration=self._current_iteration)
            
            # Get response from provider
            messages = self.session.get_messages_for_provider()
            
            response = await self.provider.complete(
                messages=messages,
                tools=self.tools if self.tools else None,
                temperature=self.config.temperature,
                **self.config.options,
            )
            
            # Track token usage
            self.session.add_token_usage(
                response.usage.get("input_tokens", 0),
                response.usage.get("output_tokens", 0),
            )
            step.token_usage = response.usage
            
            # Handle tool calls
            if response.tool_calls:
                step.tool_calls = [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in response.tool_calls
                ]
                
                # Add assistant message with tool calls
                self.session.add_message(
                    "assistant",
                    response.content,
                    tool_calls=step.tool_calls,
                )
                
                if self.on_message:
                    self.on_message("assistant", response.content)
                
                # Execute tool calls
                for tool_call in response.tool_calls:
                    if self.on_tool_call:
                        self.on_tool_call(tool_call.name, tool_call.arguments)
                    
                    # Create tool context
                    ctx = ToolContext(
                        session_id=self.session.id,
                        message_id=tool_call.id,
                        agent=self.config.name,
                    )
                    
                    result = await ToolRegistry.execute(
                        tool_call.name,
                        ctx,
                        **tool_call.arguments,
                    )
                    
                    step.tool_results.append({
                        "tool_call_id": tool_call.id,
                        "content": result.content,
                        "is_error": result.status == ToolStatus.ERROR,
                    })
                    
                    if self.on_tool_result:
                        self.on_tool_result(tool_call.name, result)
                
                # Add tool results to session
                tool_results_content = self._format_tool_results(step.tool_results)
                self.session.add_message(
                    "user",
                    tool_results_content,
                    tool_results=step.tool_results,
                )
                
            else:
                # No tool calls, return final response
                step.assistant_message = response.content
                
                if response.content:
                    self.session.add_message("assistant", response.content)
                    
                    if self.on_message:
                        self.on_message("assistant", response.content)
                
                self._steps.append(step)
                return response.content
        
        # Max iterations reached
        self._steps.append(AgentStep(
            iteration=self._current_iteration,
            assistant_message="Max iterations reached",
        ))
        return "Max iterations reached. Please refine your request."
    
    async def run_stream(self, user_message: str) -> AsyncIterator[str]:
        """
        Run the agent with streaming response.
        
        Yields tokens as they are generated.
        """
        # Add user message to session
        self.session.add_message("user", user_message)
        
        if self.on_message:
            self.on_message("user", user_message)
        
        self._current_iteration = 0
        
        while self._current_iteration < self.config.max_iterations:
            self._current_iteration += 1
            
            step = AgentStep(iteration=self._current_iteration)
            messages = self.session.get_messages_for_provider()
            
            # Stream response
            full_content = ""
            tool_calls = []
            
            # Note: Streaming with tools is complex, we'll use complete for now
            # when tool calls are expected
            if self.tools:
                response = await self.provider.complete(
                    messages=messages,
                    tools=self.tools,
                    temperature=self.config.temperature,
                    **self.config.options,
                )
                full_content = response.content
                tool_calls = response.tool_calls
                
                # Track token usage
                self.session.add_token_usage(
                    response.usage.get("input_tokens", 0),
                    response.usage.get("output_tokens", 0),
                )
            else:
                # Stream without tools
                async for token in self.provider.stream(
                    messages=messages,
                    temperature=self.config.temperature,
                    **self.config.options,
                ):
                    full_content += token
                    yield token
            
            # Handle tool calls
            if tool_calls:
                step.tool_calls = [
                    {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                    for tc in tool_calls
                ]
                
                self.session.add_message(
                    "assistant",
                    full_content,
                    tool_calls=step.tool_calls,
                )
                
                if self.on_message:
                    self.on_message("assistant", full_content)
                
                # Execute tool calls
                for tool_call in tool_calls:
                    if self.on_tool_call:
                        self.on_tool_call(tool_call.name, tool_call.arguments)
                    
                    # Create tool context
                    ctx = ToolContext(
                        session_id=self.session.id,
                        message_id=tool_call.id,
                        agent=self.config.name,
                    )
                    
                    result = await ToolRegistry.execute(
                        tool_call.name,
                        ctx,
                        **tool_call.arguments,
                    )
                    
                    step.tool_results.append({
                        "tool_call_id": tool_call.id,
                        "content": result.content,
                        "is_error": result.status == ToolStatus.ERROR,
                    })
                    
                    if self.on_tool_result:
                        self.on_tool_result(tool_call.name, result)
                
                # Add tool results to session
                tool_results_content = self._format_tool_results(step.tool_results)
                self.session.add_message(
                    "user",
                    tool_results_content,
                    tool_results=step.tool_results,
                )
                
            else:
                # No tool calls, finish
                step.assistant_message = full_content
                self._steps.append(step)
                
                if not self.tools:
                    # Already yielded during streaming
                    return
                
                # Yield remaining content if not streaming
                if full_content and not self.on_message:
                    yield full_content
                
                return
        
        # Max iterations reached
        yield "\n[Max iterations reached]"
    
    def _format_tool_results(self, tool_results: list[dict]) -> str:
        """Format tool results for the LLM."""
        parts = []
        for result in tool_results:
            status = "Error" if result["is_error"] else "Success"
            parts.append(f"Tool {result.get('tool_call_id', 'unknown')} ({status}):")
            parts.append(str(result["content"]))
        return "\n\n".join(parts)
    
    def get_history(self) -> list[dict]:
        """Get conversation history."""
        return [m.to_dict() for m in self.session.get_messages()]
    
    def get_steps(self) -> list[AgentStep]:
        """Get execution steps."""
        return self._steps
    
    def reset(self) -> None:
        """Reset the agent state."""
        self.session.clear()
        self._steps = []
        self._current_iteration = 0
        
        # Re-add system prompt
        if self.config.system_prompt:
            self.session.add_message("system", self.config.system_prompt)
    
    def save_session(self) -> Path:
        """Save current session to disk."""
        return self.session.save()
    
    @property
    def token_usage(self) -> dict:
        """Get total token usage."""
        return self.session.token_usage.to_dict()


# Built-in agent definitions
BUILTIN_AGENTS: dict[str, AgentInfo] = {
    "build": AgentInfo(
        name="build",
        description="The default agent. Executes tools based on configured permissions.",
        mode=AgentMode.PRIMARY,
        native=True,
        options={},
    ),
    "plan": AgentInfo(
        name="plan",
        description="Plan mode. Disallows all edit tools.",
        mode=AgentMode.PRIMARY,
        native=True,
        options={},
    ),
    "general": AgentInfo(
        name="general",
        description="General-purpose agent for researching complex questions and executing multi-step tasks.",
        mode=AgentMode.SUBAGENT,
        native=True,
        options={},
    ),
    "explore": AgentInfo(
        name="explore",
        description="Fast agent specialized for exploring codebases. Use this when you need to quickly find files by patterns or search code.",
        mode=AgentMode.SUBAGENT,
        native=True,
        prompt_file="explore.txt",
        options={},
    ),
    "compaction": AgentInfo(
        name="compaction",
        mode=AgentMode.PRIMARY,
        native=True,
        hidden=True,
        prompt_file="compaction.txt",
        options={},
    ),
    "title": AgentInfo(
        name="title",
        mode=AgentMode.PRIMARY,
        native=True,
        hidden=True,
        temperature=0.5,
        prompt_file="title.txt",
        options={},
    ),
    "summary": AgentInfo(
        name="summary",
        mode=AgentMode.PRIMARY,
        native=True,
        hidden=True,
        prompt_file="summary.txt",
        options={},
    ),
}


class AgentRegistry:
    """Registry for managing agents."""
    
    _agents: dict[str, AgentInfo] = BUILTIN_AGENTS.copy()
    _prompt_dir: Optional[Path] = None
    
    @classmethod
    def set_prompt_dir(cls, path: Path) -> None:
        """Set the prompt directory."""
        cls._prompt_dir = path
    
    @classmethod
    def register(cls, info: AgentInfo) -> None:
        """Register a new agent."""
        cls._agents[info.name] = info
    
    @classmethod
    def get(cls, name: str) -> Optional[AgentInfo]:
        """Get an agent by name."""
        return cls._agents.get(name)
    
    @classmethod
    def list(cls) -> list[AgentInfo]:
        """List all agents."""
        return list(cls._agents.values())
    
    @classmethod
    def get_prompt(cls, agent_name: str) -> Optional[str]:
        """Get the prompt template for an agent."""
        agent = cls.get(agent_name)
        if not agent or not agent.prompt_file:
            return None
        
        if cls._prompt_dir:
            prompt_path = cls._prompt_dir / agent.prompt_file
            if prompt_path.exists():
                return prompt_path.read_text()
        
        # Try default locations
        default_dirs = [
            Path(__file__).parent / "prompt",
            Path.cwd() / ".opencode" / "prompts",
        ]
        
        for dir_path in default_dirs:
            prompt_path = dir_path / agent.prompt_file
            if prompt_path.exists():
                return prompt_path.read_text()
        
        return None
    
    @classmethod
    def default_agent(cls) -> str:
        """Get the default agent name."""
        # Try to get from environment or config
        default = os.environ.get("OPENCODE_DEFAULT_AGENT", "build")
        agent = cls.get(default)
        if agent and agent.mode != AgentMode.SUBAGENT and not agent.hidden:
            return default
        
        # Fall back to first primary visible agent
        for name, agent in cls._agents.items():
            if agent.mode != AgentMode.SUBAGENT and not agent.hidden:
                return name
        
        return "build"


async def get_agent(name: str) -> Optional[AgentInfo]:
    """Get an agent by name."""
    return AgentRegistry.get(name)


async def list_agents() -> list[AgentInfo]:
    """List all available agents."""
    return AgentRegistry.list()


async def get_default_agent() -> str:
    """Get the default agent name."""
    return AgentRegistry.default_agent()
