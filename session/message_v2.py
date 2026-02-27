"""
Message V2 module for OpenCode.

Handles message and part management including:
- Message types (User, Assistant)
- Part types (Text, Tool, File, Reasoning, etc.)
- Message streaming and filtering
- Error handling and conversion
"""

import json
from typing import Any, Optional, AsyncIterator
from pydantic import BaseModel, Field


class MessageV2Error(BaseModel):
    """Base class for message errors."""
    name: str
    message: str


class OutputLengthError(MessageV2Error):
    """Error when output exceeds length limit."""
    name: str = "MessageOutputLengthError"


class AbortedError(MessageV2Error):
    """Error when operation is aborted."""
    name: str = "MessageAbortedError"
    message: str


class StructuredOutputError(MessageV2Error):
    """Error when structured output fails."""
    name: str = "StructuredOutputError"
    message: str
    retries: int


class AuthError(MessageV2Error):
    """Error when authentication fails."""
    name: str = "ProviderAuthError"
    providerID: str
    message: str


class APIError(MessageV2Error):
    """Error from API call."""
    name: str = "APIError"
    message: str
    statusCode: Optional[int] = None
    isRetryable: bool = False
    responseHeaders: Optional[dict[str, str]] = None
    responseBody: Optional[str] = None
    metadata: Optional[dict[str, str]] = None


class ContextOverflowError(MessageV2Error):
    """Error when context overflows."""
    name: str = "ContextOverflowError"
    message: str
    responseBody: Optional[str] = None


# Output format types
class OutputFormatText(BaseModel):
    """Text output format."""
    type: str = "text"


class OutputFormatJsonSchema(BaseModel):
    """JSON schema output format."""
    type: str = "json_schema"
    schema: dict[str, Any]
    retryCount: int = Field(default=2, ge=0)


OutputFormat = OutputFormatText | OutputFormatJsonSchema


# Part types
class PartBase(BaseModel):
    """Base class for all parts."""
    id: str
    sessionID: str
    messageID: str


class TextPart(PartBase):
    """Text part."""
    type: str = "text"
    text: str
    synthetic: Optional[bool] = None
    ignored: Optional[bool] = None
    time: Optional[dict] = None
    metadata: Optional[dict] = None


class ReasoningPart(PartBase):
    """Reasoning part."""
    type: str = "reasoning"
    text: str
    metadata: Optional[dict] = None
    time: dict


class FilePartSourceText(BaseModel):
    """File part source text."""
    value: str
    start: int
    end: int


class FileSource(BaseModel):
    """File source."""
    type: str = "file"
    path: str
    text: FilePartSourceText


class SymbolSource(BaseModel):
    """Symbol source."""
    type: str = "symbol"
    path: str
    range: dict
    name: str
    kind: int
    text: FilePartSourceText


class ResourceSource(BaseModel):
    """Resource source."""
    type: str = "resource"
    clientName: str
    uri: str
    text: FilePartSourceText


FilePartSource = FileSource | SymbolSource | ResourceSource


class FilePart(PartBase):
    """File part."""
    type: str = "file"
    mime: str
    filename: Optional[str] = None
    url: str
    source: Optional[FilePartSource] = None


class AgentPart(PartBase):
    """Agent part."""
    type: str = "agent"
    name: str
    source: Optional[dict] = None


class CompactionPart(PartBase):
    """Compaction part."""
    type: str = "compaction"
    auto: bool


class SubtaskPart(PartBase):
    """Subtask part."""
    type: str = "subtask"
    prompt: str
    description: str
    agent: str
    model: Optional[dict] = None
    command: Optional[str] = None


class RetryPart(PartBase):
    """Retry part."""
    type: str = "retry"
    attempt: int
    error: dict
    time: dict


class StepStartPart(PartBase):
    """Step start part."""
    type: str = "step-start"
    snapshot: Optional[str] = None


class StepFinishPart(PartBase):
    """Step finish part."""
    type: str = "step-finish"
    reason: str
    snapshot: Optional[str] = None
    cost: float
    tokens: dict


class SnapshotPart(PartBase):
    """Snapshot part."""
    type: str = "snapshot"
    snapshot: str


class PatchPart(PartBase):
    """Patch part."""
    type: str = "patch"
    hash: str
    files: list[str]


# Tool state types
class ToolStatePending(BaseModel):
    """Pending tool state."""
    status: str = "pending"
    input: dict[str, Any]
    raw: str


class ToolStateRunning(BaseModel):
    """Running tool state."""
    status: str = "running"
    input: dict[str, Any]
    title: Optional[str] = None
    metadata: Optional[dict] = None
    time: dict


class ToolStateCompleted(BaseModel):
    """Completed tool state."""
    status: str = "completed"
    input: dict[str, Any]
    output: str
    title: str
    metadata: dict
    time: dict
    attachments: Optional[list[FilePart]] = None


class ToolStateError(BaseModel):
    """Error tool state."""
    status: str = "error"
    input: dict[str, Any]
    error: str
    metadata: Optional[dict] = None
    time: dict


ToolState = ToolStatePending | ToolStateRunning | ToolStateCompleted | ToolStateError


class ToolPart(PartBase):
    """Tool part."""
    type: str = "tool"
    callID: str
    tool: str
    state: ToolState
    metadata: Optional[dict] = None


# Union of all part types
Part = TextPart | ReasoningPart | FilePart | AgentPart | CompactionPart | SubtaskPart | RetryPart | StepStartPart | StepFinishPart | SnapshotPart | PatchPart | ToolPart


# Message types
class MessageBase(BaseModel):
    """Base class for messages."""
    id: str
    sessionID: str


class UserMessage(MessageBase):
    """User message."""
    role: str = "user"
    time: dict
    format: Optional[OutputFormat] = None
    summary: Optional[dict] = None
    agent: str
    model: dict
    system: Optional[str] = None
    tools: Optional[dict[str, bool]] = None
    variant: Optional[str] = None


class AssistantMessage(MessageBase):
    """Assistant message."""
    role: str = "assistant"
    time: dict
    error: Optional[MessageV2Error] = None
    parentID: str
    modelID: str
    providerID: str
    mode: str
    agent: str
    path: dict
    summary: Optional[bool] = None
    cost: float = 0.0
    tokens: dict
    structured: Optional[Any] = None
    variant: Optional[str] = None
    finish: Optional[str] = None


Info = UserMessage | AssistantMessage


class MessageWithParts(BaseModel):
    """Message with parts."""
    info: Info
    parts: list[Part]


def filter_compacted(messages: list[MessageWithParts]) -> list[MessageWithParts]:
    """Filter out compacted messages."""
    result = []
    completed = set()
    
    for msg in messages:
        result.append(msg)
        
        if (
            msg.info.role == "user"
            and msg.info.id in completed
            and any(p.type == "compaction" for p in msg.parts)
        ):
            break
        
        if (
            msg.info.role == "assistant"
            and getattr(msg.info, "summary", None)
            and getattr(msg.info, "finish", None)
        ):
            completed.add(getattr(msg.info, "parentID", ""))
    
    result.reverse()
    return result


def from_error(e: Exception, ctx: dict) -> MessageV2Error:
    """Convert an exception to a MessageV2Error."""
    error_name = type(e).__name__
    
    if error_name == "DOMException" and getattr(e, "name", "") == "AbortError":
        return AbortedError(message=str(e))
    
    if isinstance(e, OutputLengthError):
        return e
    
    if "API_KEY" in str(e) or "auth" in str(e).lower():
        return AuthError(providerID=ctx.get("providerID", "unknown"), message=str(e))
    
    if "ECONNRESET" in str(e):
        return APIError(
            message="Connection reset by server",
            isRetryable=True,
            metadata={
                "code": getattr(e, "code", ""),
                "syscall": getattr(e, "syscall", ""),
                "message": str(e),
            },
        )
    
    if "context" in str(e).lower() and ("overflow" in str(e).lower() or "exceed" in str(e).lower()):
        return ContextOverflowError(message=str(e))
    
    # Default to APIError for HTTP errors
    if hasattr(e, "status_code"):
        return APIError(
            message=str(e),
            statusCode=getattr(e, "status_code", None),
            isRetryable=getattr(e, "status_code", 500) >= 500,
        )
    
    # Generic error
    return MessageV2Error(name="UnknownError", message=str(e))


# Model message conversion
def to_model_messages(messages: list[MessageWithParts], model: dict) -> list[dict]:
    """Convert messages to model format for provider API."""
    result = []
    tool_names = set()
    
    for msg in messages:
        if not msg.parts:
            continue
        
        if msg.info.role == "user":
            user_message = {
                "id": msg.info.id,
                "role": "user",
                "content": [],
            }
            
            for part in msg.parts:
                if part.type == "text" and not getattr(part, "ignored", False):
                    user_message["content"].append({
                        "type": "text",
                        "text": part.text,
                    })
                
                if part.type == "file" and part.mime not in ["text/plain", "application/x-directory"]:
                    user_message["content"].append({
                        "type": "file",
                        "url": part.url,
                        "mediaType": part.mime,
                        "filename": part.filename,
                    })
                
                if part.type == "compaction":
                    user_message["content"].append({
                        "type": "text",
                        "text": "What did we do so far?",
                    })
                
                if part.type == "subtask":
                    user_message["content"].append({
                        "type": "text",
                        "text": "The following tool was executed by the user",
                    })
            
            if user_message["content"]:
                result.append(user_message)
        
        if msg.info.role == "assistant":
            if getattr(msg.info, "error", None):
                error = msg.info.error
                if not (
                    isinstance(error, AbortedError)
                    and any(p.type not in ["step-start", "reasoning"] for p in msg.parts)
                ):
                    continue
            
            assistant_message = {
                "id": msg.info.id,
                "role": "assistant",
                "content": [],
            }
            
            for part in msg.parts:
                if part.type == "text":
                    assistant_message["content"].append({
                        "type": "text",
                        "text": part.text,
                    })
                
                if part.type == "step-start":
                    assistant_message["content"].append({
                        "type": "step-start",
                    })
                
                if part.type == "tool":
                    tool_names.add(part.tool)
                    
                    if part.state.status == "completed":
                        assistant_message["content"].append({
                            "type": f"tool-{part.tool}",
                            "state": "output-available",
                            "toolCallId": part.callID,
                            "input": part.state.input,
                            "output": part.state.output,
                        })
                    
                    if part.state.status == "error":
                        assistant_message["content"].append({
                            "type": f"tool-{part.tool}",
                            "state": "output-error",
                            "toolCallId": part.callID,
                            "input": part.state.input,
                            "errorText": part.state.error,
                        })
                    
                    if part.state.status in ["pending", "running"]:
                        assistant_message["content"].append({
                            "type": f"tool-{part.tool}",
                            "state": "output-error",
                            "toolCallId": part.callID,
                            "input": part.state.input,
                            "errorText": "[Tool execution was interrupted]",
                        })
                
                if part.type == "reasoning":
                    assistant_message["content"].append({
                        "type": "reasoning",
                        "text": part.text,
                    })
            
            if assistant_message["content"]:
                result.append(assistant_message)
    
    return result


class MessageEvents:
    """Message bus events."""
    
    @staticmethod
    def define(name: str, schema: dict):
        """Define a bus event."""
        return {"name": name, "schema": schema}
    
    Updated = define("message.updated", {"info": dict})
    Removed = define("message.removed", {"sessionID": str, "messageID": str})
    PartUpdated = define("message.part.updated", {"part": dict})
    PartDelta = define("message.part.delta", {
        "sessionID": str,
        "messageID": str,
        "partID": str,
        "field": str,
        "delta": str,
    })
    PartRemoved = define("message.part.removed", {
        "sessionID": str,
        "messageID": str,
        "partID": str,
    })
