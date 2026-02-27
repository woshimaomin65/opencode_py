"""
Database models for OpenCode Session module.

Defines SQLAlchemy models for:
- Session table
- Message table
- Part table
- Todo table
- Permission table
"""

from datetime import datetime
from typing import Optional, Any
from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    JSON,
)
from sqlalchemy.orm import relationship, declarative_base
from pydantic import BaseModel, Field
from enum import Enum

Base = declarative_base()


class SessionModel(Base):
    """Session table model."""
    
    __tablename__ = "session"
    
    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("project.id", ondelete="cascade"), nullable=False)
    parent_id = Column(String, nullable=True)
    slug = Column(String, nullable=False)
    directory = Column(String, nullable=False)
    title = Column(String, nullable=False)
    version = Column(String, nullable=False)
    share_url = Column(String, nullable=True)
    summary_additions = Column(Integer, nullable=True)
    summary_deletions = Column(Integer, nullable=True)
    summary_files = Column(Integer, nullable=True)
    summary_diffs = Column(JSON, nullable=True)  # List[Snapshot.FileDiff]
    revert = Column(JSON, nullable=True)  # {messageID, partID, snapshot, diff}
    permission = Column(JSON, nullable=True)  # PermissionNext.Ruleset
    time_created = Column(Integer, nullable=False)
    time_updated = Column(Integer, nullable=False)
    time_compacting = Column(Integer, nullable=True)
    time_archived = Column(Integer, nullable=True)
    
    # Relationships
    messages = relationship("MessageModel", back_populates="session", cascade="all, delete-orphan")
    todos = relationship("TodoModel", back_populates="session", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("session_project_idx", "project_id"),
        Index("session_parent_idx", "parent_id"),
    )


class MessageModel(Base):
    """Message table model."""
    
    __tablename__ = "message"
    
    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("session.id", ondelete="cascade"), nullable=False)
    time_created = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)  # MessageV2.Info without id and sessionID
    
    # Relationships
    session = relationship("SessionModel", back_populates="messages")
    parts = relationship("PartModel", back_populates="message", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("message_session_idx", "session_id"),
    )


class PartModel(Base):
    """Part table model."""
    
    __tablename__ = "part"
    
    id = Column(String, primary_key=True)
    message_id = Column(String, ForeignKey("message.id", ondelete="cascade"), nullable=False)
    session_id = Column(String, nullable=False)
    time_created = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)  # MessageV2.Part without id, sessionID, messageID
    
    # Relationships
    message = relationship("MessageModel", back_populates="parts")
    
    __table_args__ = (
        Index("part_message_idx", "message_id"),
        Index("part_session_idx", "session_id"),
    )


class TodoStatus(str, Enum):
    """Todo status enum."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TodoPriority(str, Enum):
    """Todo priority enum."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TodoModel(Base):
    """Todo table model."""
    
    __tablename__ = "todo"
    
    session_id = Column(String, ForeignKey("session.id", ondelete="cascade"), nullable=False)
    content = Column(String, nullable=False)
    status = Column(String, nullable=False)  # TodoStatus
    priority = Column(String, nullable=False)  # TodoPriority
    position = Column(Integer, nullable=False)
    time_created = Column(Integer, nullable=False)
    time_updated = Column(Integer, nullable=False)
    
    # Relationships
    session = relationship("SessionModel", back_populates="todos")
    
    __table_args__ = (
        PrimaryKeyConstraint("session_id", "position"),
        Index("todo_session_idx", "session_id"),
    )


class PermissionModel(Base):
    """Permission table model."""
    
    __tablename__ = "permission"
    
    project_id = Column(String, ForeignKey("project.id", ondelete="cascade"), primary_key=True)
    time_created = Column(Integer, nullable=False)
    time_updated = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)  # PermissionNext.Ruleset


# Pydantic models for validation and serialization

class SessionSummary(BaseModel):
    """Session summary data."""
    additions: int = 0
    deletions: int = 0
    files: int = 0
    diffs: Optional[list[dict]] = None


class SessionShare(BaseModel):
    """Session share data."""
    url: str


class SessionRevert(BaseModel):
    """Session revert data."""
    messageID: str
    partID: Optional[str] = None
    snapshot: Optional[str] = None
    diff: Optional[str] = None


class SessionTime(BaseModel):
    """Session time data."""
    created: int
    updated: int
    compacting: Optional[int] = None
    archived: Optional[int] = None


class SessionInfo(BaseModel):
    """Session info model."""
    id: str
    slug: str
    projectID: str
    directory: str
    parentID: Optional[str] = None
    summary: Optional[SessionSummary] = None
    share: Optional[SessionShare] = None
    title: str
    version: str
    time: SessionTime
    permission: Optional[list[dict]] = None
    revert: Optional[SessionRevert] = None
    
    class Config:
        from_attributes = True


class MessageTime(BaseModel):
    """Message time data."""
    created: int
    completed: Optional[int] = None


class MessageTokens(BaseModel):
    """Message token data."""
    total: Optional[int] = None
    input: int
    output: int
    reasoning: int = 0
    cache: dict[str, int] = Field(default_factory=lambda: {"read": 0, "write": 0})


class MessagePath(BaseModel):
    """Message path data."""
    cwd: str
    root: str


class MessageModelInfo(BaseModel):
    """Message model info."""
    providerID: str
    modelID: str


class UserMessage(BaseModel):
    """User message model."""
    id: str
    sessionID: str
    role: str = "user"
    time: MessageTime
    format: Optional[dict] = None
    summary: Optional[dict] = None
    agent: str
    model: MessageModelInfo
    system: Optional[str] = None
    tools: Optional[dict[str, bool]] = None
    variant: Optional[str] = None


class AssistantMessage(BaseModel):
    """Assistant message model."""
    id: str
    sessionID: str
    role: str = "assistant"
    time: MessageTime
    error: Optional[dict] = None
    parentID: str
    modelID: str
    providerID: str
    mode: str
    agent: str
    path: MessagePath
    summary: Optional[bool] = None
    cost: float = 0.0
    tokens: MessageTokens
    structured: Optional[Any] = None
    variant: Optional[str] = None
    finish: Optional[str] = None


# Part types
class TextPart(BaseModel):
    """Text part model."""
    id: str
    sessionID: str
    messageID: str
    type: str = "text"
    text: str
    synthetic: Optional[bool] = None
    ignored: Optional[bool] = None
    time: Optional[dict] = None
    metadata: Optional[dict] = None


class ToolPart(BaseModel):
    """Tool part model."""
    id: str
    sessionID: str
    messageID: str
    type: str = "tool"
    callID: str
    tool: str
    state: dict
    metadata: Optional[dict] = None


class FilePart(BaseModel):
    """File part model."""
    id: str
    sessionID: str
    messageID: str
    type: str = "file"
    mime: str
    filename: Optional[str] = None
    url: str
    source: Optional[dict] = None


class ReasoningPart(BaseModel):
    """Reasoning part model."""
    id: str
    sessionID: str
    messageID: str
    type: str = "reasoning"
    text: str
    metadata: Optional[dict] = None
    time: dict


class SubtaskPart(BaseModel):
    """Subtask part model."""
    id: str
    sessionID: str
    messageID: str
    type: str = "subtask"
    prompt: str
    description: str
    agent: str
    model: Optional[MessageModelInfo] = None
    command: Optional[str] = None


class CompactionPart(BaseModel):
    """Compaction part model."""
    id: str
    sessionID: str
    messageID: str
    type: str = "compaction"
    auto: bool


class StepStartPart(BaseModel):
    """Step start part model."""
    id: str
    sessionID: str
    messageID: str
    type: str = "step-start"
    snapshot: Optional[str] = None


class StepFinishPart(BaseModel):
    """Step finish part model."""
    id: str
    sessionID: str
    messageID: str
    type: str = "step-finish"
    reason: str
    snapshot: Optional[str] = None
    cost: float
    tokens: dict


class RetryPart(BaseModel):
    """Retry part model."""
    id: str
    sessionID: str
    messageID: str
    type: str = "retry"
    attempt: int
    error: dict
    time: dict


class SnapshotPart(BaseModel):
    """Snapshot part model."""
    id: str
    sessionID: str
    messageID: str
    type: str = "snapshot"
    snapshot: str


class PatchPart(BaseModel):
    """Patch part model."""
    id: str
    sessionID: str
    messageID: str
    type: str = "patch"
    hash: str
    files: list[str]


class AgentPart(BaseModel):
    """Agent part model."""
    id: str
    sessionID: str
    messageID: str
    type: str = "agent"
    name: str
    source: Optional[dict] = None
