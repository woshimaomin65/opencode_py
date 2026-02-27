"""
Session module for OpenCode.

Handles session management including:
- Session creation and loading
- Message history
- Token tracking
- Session persistence
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field, asdict
from pydantic import BaseModel


@dataclass
class Message:
    """A message in a session."""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_calls: Optional[list[dict]] = None
    tool_results: Optional[list[dict]] = None
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "tool_calls": self.tool_calls,
            "tool_results": self.tool_results,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
            tool_calls=data.get("tool_calls"),
            tool_results=data.get("tool_results"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TokenUsage:
    """Token usage tracking."""
    input_tokens: int = 0
    output_tokens: int = 0
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
    
    def add(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )
    
    def to_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class SessionState:
    """Session state."""
    id: str
    model: str
    provider: str
    created_at: datetime
    updated_at: datetime
    messages: list[Message]
    token_usage: TokenUsage
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "model": self.model,
            "provider": self.provider,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "messages": [m.to_dict() for m in self.messages],
            "token_usage": self.token_usage.to_dict(),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        return cls(
            id=data["id"],
            model=data["model"],
            provider=data["provider"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            messages=[Message.from_dict(m) for m in data["messages"]],
            token_usage=TokenUsage(
                input_tokens=data["token_usage"]["input_tokens"],
                output_tokens=data["token_usage"]["output_tokens"],
            ),
            metadata=data.get("metadata", {}),
        )


class Session:
    """
    Session manager for conversations.
    
    Handles:
    - Creating and loading sessions
    - Adding messages
    - Tracking token usage
    - Persisting sessions to disk
    """
    
    def __init__(
        self,
        session_id: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        provider: str = "anthropic",
        storage_path: Optional[Path] = None,
    ):
        self.id = session_id or str(uuid.uuid4())
        self.model = model
        self.provider = provider
        self.storage_path = storage_path or Path.cwd() / ".opencode" / "sessions"
        
        self.created_at = datetime.now()
        self.updated_at = self.created_at
        self.messages: list[Message] = []
        self.token_usage = TokenUsage()
        self.metadata: dict = {}
        
        # Ensure storage directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def create(
        cls,
        model: str = "claude-sonnet-4-20250514",
        provider: str = "anthropic",
        storage_path: Optional[Path] = None,
    ) -> "Session":
        """Create a new session."""
        return cls(
            model=model,
            provider=provider,
            storage_path=storage_path,
        )
    
    @classmethod
    def load(cls, session_id: str, storage_path: Optional[Path] = None) -> Optional["Session"]:
        """Load an existing session from disk."""
        storage_path = storage_path or Path.cwd() / ".opencode" / "sessions"
        session_file = storage_path / f"{session_id}.json"
        
        if not session_file.exists():
            return None
        
        try:
            with open(session_file, 'r') as f:
                data = json.load(f)
            
            state = SessionState.from_dict(data)
            
            session = cls(
                session_id=state.id,
                model=state.model,
                provider=state.provider,
                storage_path=storage_path,
            )
            session.created_at = state.created_at
            session.updated_at = state.updated_at
            session.messages = state.messages
            session.token_usage = state.token_usage
            session.metadata = state.metadata
            
            return session
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Failed to load session: {e}")
            return None
    
    def add_message(
        self,
        role: str,
        content: str,
        tool_calls: Optional[list[dict]] = None,
        tool_results: Optional[list[dict]] = None,
        metadata: Optional[dict] = None,
    ) -> Message:
        """Add a message to the session."""
        message = Message(
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_results=tool_results,
            metadata=metadata or {},
        )
        self.messages.append(message)
        self.updated_at = datetime.now()
        return message
    
    def add_token_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Add token usage to the session."""
        self.token_usage = TokenUsage(
            input_tokens=self.token_usage.input_tokens + input_tokens,
            output_tokens=self.token_usage.output_tokens + output_tokens,
        )
    
    def get_messages(self, limit: Optional[int] = None) -> list[Message]:
        """Get messages from the session."""
        if limit:
            return self.messages[-limit:]
        return self.messages
    
    def get_messages_for_provider(self) -> list[dict]:
        """Get messages formatted for provider API."""
        return [
            {
                "role": m.role,
                "content": m.content,
            }
            for m in self.messages
        ]
    
    def save(self) -> Path:
        """Save session to disk."""
        session_file = self.storage_path / f"{self.id}.json"
        
        state = SessionState(
            id=self.id,
            model=self.model,
            provider=self.provider,
            created_at=self.created_at,
            updated_at=self.updated_at,
            messages=self.messages,
            token_usage=self.token_usage,
            metadata=self.metadata,
        )
        
        with open(session_file, 'w') as f:
            json.dump(state.to_dict(), f, indent=2)
        
        return session_file
    
    def delete(self) -> bool:
        """Delete the session from disk."""
        session_file = self.storage_path / f"{self.id}.json"
        
        if session_file.exists():
            session_file.unlink()
            return True
        return False
    
    def clear(self) -> None:
        """Clear all messages from the session."""
        self.messages = []
        self.token_usage = TokenUsage()
        self.updated_at = datetime.now()
    
    @property
    def state(self) -> SessionState:
        """Get current session state."""
        return SessionState(
            id=self.id,
            model=self.model,
            provider=self.provider,
            created_at=self.created_at,
            updated_at=self.updated_at,
            messages=self.messages,
            token_usage=self.token_usage,
            metadata=self.metadata,
        )
    
    def __repr__(self) -> str:
        return f"Session(id={self.id}, messages={len(self.messages)}, tokens={self.token_usage.total_tokens})"


class SessionManager:
    """Manager for multiple sessions."""
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path.cwd() / ".opencode" / "sessions"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, Session] = {}
    
    def create_session(
        self,
        model: str = "claude-sonnet-4-20250514",
        provider: str = "anthropic",
    ) -> Session:
        """Create a new session."""
        session = Session.create(
            model=model,
            provider=provider,
            storage_path=self.storage_path,
        )
        self._sessions[session.id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        if session_id in self._sessions:
            return self._sessions[session_id]
        
        # Try to load from disk
        session = Session.load(session_id, self.storage_path)
        if session:
            self._sessions[session_id] = session
        return session
    
    def list_sessions(self) -> list[dict]:
        """List all sessions."""
        sessions = []
        
        # In-memory sessions
        for session in self._sessions.values():
            sessions.append({
                "id": session.id,
                "model": session.model,
                "provider": session.provider,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "message_count": len(session.messages),
                "token_count": session.token_usage.total_tokens,
            })
        
        # Disk sessions not in memory
        for session_file in self.storage_path.glob("*.json"):
            session_id = session_file.stem
            if session_id not in self._sessions:
                try:
                    with open(session_file, 'r') as f:
                        data = json.load(f)
                    sessions.append({
                        "id": data["id"],
                        "model": data["model"],
                        "provider": data["provider"],
                        "created_at": data["created_at"],
                        "updated_at": data["updated_at"],
                        "message_count": len(data["messages"]),
                        "token_count": data["token_usage"]["total_tokens"],
                    })
                except (json.JSONDecodeError, KeyError):
                    continue
        
        return sorted(sessions, key=lambda x: x["updated_at"], reverse=True)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            self._sessions[session_id].delete()
            del self._sessions[session_id]
            return True
        
        session = Session.load(session_id, self.storage_path)
        if session:
            return session.delete()
        
        return False
