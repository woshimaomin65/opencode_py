"""
Session module for OpenCode.

Provides session management functionality:
- Session creation, loading, and persistence
- Message and part management
- Token tracking
- Database integration via SQLAlchemy
"""

from typing import Optional

from .models import (
    # Database models
    Base,
    SessionModel,
    MessageModel,
    PartModel,
    TodoModel,
    PermissionModel,
    # Pydantic models
    SessionInfo,
    SessionSummary,
    SessionShare,
    SessionRevert,
    SessionTime,
    UserMessage,
    AssistantMessage,
    TextPart,
    ToolPart,
    FilePart,
    ReasoningPart,
    SubtaskPart,
    CompactionPart,
    StepStartPart,
    StepFinishPart,
    RetryPart,
    SnapshotPart,
    PatchPart,
    AgentPart,
)

from .session import (
    Session,
    SessionState,
)

from .manager import (
    # Classes
    SessionManager,
    Database,
    NotFoundError,
    BusyError,
    SessionEvents,
    MessageEvents,
    # Functions
    from_row,
    to_row,
    get_forked_title,
    create_default_title,
    is_default_title,
    get_manager,
    create_session,
    get_session,
)


def calculate_usage(model: dict, usage: dict, metadata: Optional[dict] = None) -> dict:
    """Calculate token usage and cost."""
    return SessionManager.calculate_usage(model, usage, metadata)

from .message_v2 import (
    # Error types
    MessageV2Error,
    OutputLengthError,
    AbortedError,
    StructuredOutputError,
    AuthError,
    APIError,
    ContextOverflowError,
    # Format types
    OutputFormat,
    OutputFormatText,
    OutputFormatJsonSchema,
    # Part types
    Part,
    TextPart as V2TextPart,
    ReasoningPart as V2ReasoningPart,
    FilePart as V2FilePart,
    AgentPart as V2AgentPart,
    CompactionPart as V2CompactionPart,
    SubtaskPart as V2SubtaskPart,
    RetryPart as V2RetryPart,
    StepStartPart as V2StepStartPart,
    StepFinishPart as V2StepFinishPart,
    SnapshotPart as V2SnapshotPart,
    PatchPart as V2PatchPart,
    ToolPart as V2ToolPart,
    ToolState,
    ToolStatePending,
    ToolStateRunning,
    ToolStateCompleted,
    ToolStateError,
    # Message types
    Info,
    UserMessage as V2UserMessage,
    AssistantMessage as V2AssistantMessage,
    MessageWithParts,
    # Functions
    filter_compacted,
    to_model_messages,
    from_error,
)

from .prompt import (
    # Classes
    SessionPrompt,
    PromptInput,
    LoopInput,
    SessionBusyError,
    # Functions
    get_session_prompt,
    prompt,
    get_default_agent,
    get_default_model,
)


__all__ = [
    # Models
    "Base",
    "SessionModel",
    "MessageModel",
    "PartModel",
    "TodoModel",
    "PermissionModel",
    "SessionInfo",
    "SessionSummary",
    "SessionShare",
    "SessionRevert",
    "SessionTime",
    # Session classes
    "Session",
    "SessionState",
    # Manager
    "SessionManager",
    "Database",
    "NotFoundError",
    "BusyError",
    "SessionEvents",
    "MessageEvents",
    "from_row",
    "to_row",
    "get_forked_title",
    "create_default_title",
    "is_default_title",
    "get_manager",
    "create_session",
    "get_session",
    # Message V2
    "MessageV2Error",
    "OutputLengthError",
    "AbortedError",
    "StructuredOutputError",
    "AuthError",
    "APIError",
    "ContextOverflowError",
    "OutputFormat",
    "OutputFormatText",
    "OutputFormatJsonSchema",
    "Part",
    "TextPart",
    "ReasoningPart",
    "FilePart",
    "AgentPart",
    "CompactionPart",
    "SubtaskPart",
    "RetryPart",
    "StepStartPart",
    "StepFinishPart",
    "SnapshotPart",
    "PatchPart",
    "ToolPart",
    "ToolState",
    "ToolStatePending",
    "ToolStateRunning",
    "ToolStateCompleted",
    "ToolStateError",
    "Info",
    "UserMessage",
    "AssistantMessage",
    "MessageWithParts",
    "filter_compacted",
    "to_model_messages",
    "from_error",
    # Prompt
    "SessionPrompt",
    "PromptInput",
    "LoopInput",
    "SessionBusyError",
    "get_session_prompt",
    "prompt",
    "get_default_agent",
    "get_default_model",
]
