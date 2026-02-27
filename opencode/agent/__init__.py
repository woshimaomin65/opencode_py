"""
Agent module for OpenCode.

Provides AI agent functionality:
- Multiple agent types (build, plan, explore, etc.)
- Tool integration and execution
- Conversation management
- Permission handling
"""

from .agent import (
    # Enums
    AgentMode,
    # Models
    AgentInfo,
    AgentConfig,
    AgentStep,
    # Classes
    Agent,
    AgentRegistry,
    # Functions
    get_agent,
    list_agents,
    get_default_agent,
    # Constants
    BUILTIN_AGENTS,
)


__all__ = [
    # Enums
    "AgentMode",
    # Models
    "AgentInfo",
    "AgentConfig",
    "AgentStep",
    # Classes
    "Agent",
    "AgentRegistry",
    # Functions
    "get_agent",
    "list_agents",
    "get_default_agent",
    # Constants
    "BUILTIN_AGENTS",
]
