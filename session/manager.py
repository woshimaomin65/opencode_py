"""
Session module for OpenCode.

Handles session management including:
- Session creation, loading, updating, deletion
- Message and part management
- Token tracking and cost calculation
- Session persistence via SQLAlchemy
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Iterator, List, Dict
from decimal import Decimal

from sqlalchemy import create_engine, select, update, delete, and_, or_, desc, func
from sqlalchemy.orm import sessionmaker, Session as DBSession

from opencode.session.models import (
    Base,
    SessionModel,
    MessageModel,
    PartModel,
    TodoModel,
    PermissionModel,
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
from opencode.id.id import generate_id, generate_session_id, generate_message_id, generate_part_id
from opencode.util.util import slugify
from opencode.bus import Bus, BusEvent


# Bus events
class SessionEvents:
    """Session bus events."""
    
    Created = BusEvent.define("session.created", {"info": dict})
    Updated = BusEvent.define("session.updated", {"info": dict})
    Deleted = BusEvent.define("session.deleted", {"info": dict})
    Diff = BusEvent.define("session.diff", {"sessionID": str, "diff": list})
    Error = BusEvent.define("session.error", {"sessionID": Optional[str], "error": dict})


class NotFoundError(Exception):
    """Raised when a resource is not found."""
    pass


class BusyError(Exception):
    """Raised when a session is busy."""
    
    def __init__(self, session_id: str):
        super().__init__(f"Session {session_id} is busy")
        self.session_id = session_id


class Database:
    """Database manager for session operations."""
    
    _engine = None
    _session_factory = None
    _effects = []
    
    @classmethod
    def initialize(cls, db_url: str = "sqlite:///./opencode.db"):
        """Initialize the database connection."""
        cls._engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(cls._engine)
        cls._session_factory = sessionmaker(bind=cls._engine)
    
    @classmethod
    def use(cls, func):
        """Execute a function with a database session."""
        if not cls._session_factory:
            cls.initialize()
        
        session = cls._session_factory()
        try:
            result = func(session)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    @classmethod
    def effect(cls, func):
        """Register an effect to be executed after database transaction."""
        cls._effects.append(func)
    
    @classmethod
    def execute_effects(cls):
        """Execute all registered effects."""
        effects = cls._effects.copy()
        cls._effects = []
        for effect in effects:
            effect()


def from_row(row: SessionModel) -> SessionInfo:
    """Convert database row to SessionInfo."""
    summary = None
    if row.summary_additions is not None or row.summary_deletions is not None or row.summary_files is not None:
        summary = SessionSummary(
            additions=row.summary_additions or 0,
            deletions=row.summary_deletions or 0,
            files=row.summary_files or 0,
            diffs=row.summary_diffs,
        )
    
    share = SessionShare(url=row.share_url) if row.share_url else None
    revert = SessionRevert(**row.revert) if row.revert else None
    
    return SessionInfo(
        id=row.id,
        slug=row.slug,
        projectID=row.project_id,
        directory=row.directory,
        parentID=row.parent_id,
        title=row.title,
        version=row.version,
        summary=summary,
        share=share,
        revert=revert,
        permission=row.permission,
        time=SessionTime(
            created=row.time_created,
            updated=row.time_updated,
            compacting=row.time_compacting,
            archived=row.time_archived,
        ),
    )


def to_row(info: SessionInfo) -> dict:
    """Convert SessionInfo to database row dict."""
    return {
        "id": info.id,
        "project_id": info.projectID,
        "parent_id": info.parentID,
        "slug": info.slug,
        "directory": info.directory,
        "title": info.title,
        "version": info.version,
        "share_url": info.share.url if info.share else None,
        "summary_additions": info.summary.additions if info.summary else None,
        "summary_deletions": info.summary.deletions if info.summary else None,
        "summary_files": info.summary.files if info.summary else None,
        "summary_diffs": info.summary.diffs if info.summary else None,
        "revert": info.revert.model_dump() if info.revert else None,
        "permission": info.permission,
        "time_created": info.time.created,
        "time_updated": info.time.updated,
        "time_compacting": info.time.compacting,
        "time_archived": info.time.archived,
    }


def get_forked_title(title: str) -> str:
    """Generate a forked title from an existing title."""
    import re
    match = re.match(r"^(.+) \(fork #(\d+)\)$", title)
    if match:
        base = match.group(1)
        num = int(match.group(2))
        return f"{base} (fork #{num + 1})"
    return f"{title} (fork #1)"


def create_default_title(is_child: bool = False) -> str:
    """Create a default session title."""
    prefix = "Child session - " if is_child else "New session - "
    return prefix + datetime.now().isoformat()


def is_default_title(title: str) -> bool:
    """Check if a title is a default title."""
    import re
    pattern = r"^(New session - |Child session - )\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}"
    return bool(re.match(pattern, title))


class SessionManager:
    """
    Session manager for conversations.
    
    Handles:
    - Creating and loading sessions
    - Managing messages and parts
    - Tracking token usage
    - Session persistence via SQLAlchemy
    """
    
    def __init__(self, project_id: str, directory: str):
        self.project_id = project_id
        self.directory = directory
        self._busy_sessions: dict[str, bool] = {}
    
    def create(
        self,
        parent_id: Optional[str] = None,
        title: Optional[str] = None,
        permission: Optional[List[Dict]] = None,
    ) -> SessionInfo:
        """Create a new session."""
        now = int(datetime.now().timestamp() * 1000)
        
        result = SessionInfo(
            id=generate_session_id(),
            slug=slugify(),
            version="0.1.0",  # Should come from Installation
            projectID=self.project_id,
            directory=self.directory,
            parentID=parent_id,
            title=title or create_default_title(bool(parent_id)),
            permission=permission,
            time=SessionTime(
                created=now,
                updated=now,
            ),
        )
        
        def _create(db: DBSession):
            row = SessionModel(**to_row(result))
            db.add(row)
            db.flush()
            
            # Publish event
            Database.effect(lambda: Bus.publish(SessionEvents.Created, {"info": result.model_dump()}))
        
        Database.use(_create)
        Database.execute_effects()
        
        # Auto-share if configured (placeholder)
        if not parent_id:
            try:
                self.share(result.id)
            except Exception:
                pass  # Silently ignore sharing errors
        
        Bus.publish(SessionEvents.Updated, {"info": result.model_dump()})
        return result
    
    def fork(self, session_id: str, message_id: Optional[str] = None) -> SessionInfo:
        """Fork an existing session."""
        original = self.get(session_id)
        if not original:
            raise NotFoundError(f"Session not found: {session_id}")
        
        title = get_forked_title(original.title)
        forked = self.create(parent_id=None, title=title)
        
        # Copy messages up to the specified message_id
        messages = self.list_messages(session_id)
        id_map = {}
        
        for msg in messages:
            if message_id and msg["info"]["id"] >= message_id:
                break
            
            new_id = generate_message_id()
            id_map[msg["info"]["id"]] = new_id
            
            # Clone message
            msg["info"]["id"] = new_id
            msg["info"]["sessionID"] = forked.id
            if msg["info"]["role"] == "assistant" and msg["info"].get("parentID"):
                msg["info"]["parentID"] = id_map.get(msg["info"]["parentID"])
            
            self.update_message(msg["info"])
            
            # Clone parts
            for part in msg["parts"]:
                part["id"] = generate_part_id()
                part["messageID"] = new_id
                part["sessionID"] = forked.id
                self.update_part(part)
        
        return forked
    
    def get(self, session_id: str) -> Optional[SessionInfo]:
        """Get a session by ID."""
        def _get(db: DBSession):
            stmt = select(SessionModel).where(SessionModel.id == session_id)
            row = db.execute(stmt).scalar_one_or_none()
            if not row:
                raise NotFoundError(f"Session not found: {session_id}")
            return from_row(row)
        
        try:
            return Database.use(_get)
        except NotFoundError:
            return None
    
    def touch(self, session_id: str) -> SessionInfo:
        """Update session's updated timestamp."""
        now = int(datetime.now().timestamp() * 1000)
        
        def _touch(db: DBSession):
            stmt = (
                update(SessionModel)
                .where(SessionModel.id == session_id)
                .values(time_updated=now)
                .returning(SessionModel)
            )
            row = db.execute(stmt).scalar_one_or_none()
            if not row:
                raise NotFoundError(f"Session not found: {session_id}")
            
            info = from_row(row)
            Database.effect(lambda: Bus.publish(SessionEvents.Updated, {"info": info.model_dump()}))
            return info
        
        result = Database.use(_touch)
        Database.execute_effects()
        return result
    
    def set_title(self, session_id: str, title: str) -> SessionInfo:
        """Set session title."""
        def _set_title(db: DBSession):
            stmt = (
                update(SessionModel)
                .where(SessionModel.id == session_id)
                .values(title=title)
                .returning(SessionModel)
            )
            row = db.execute(stmt).scalar_one_or_none()
            if not row:
                raise NotFoundError(f"Session not found: {session_id}")
            
            info = from_row(row)
            Database.effect(lambda: Bus.publish(SessionEvents.Updated, {"info": info.model_dump()}))
            return info
        
        result = Database.use(_set_title)
        Database.execute_effects()
        return result
    
    def set_archived(self, session_id: str, time: Optional[int] = None) -> SessionInfo:
        """Set session archived status."""
        def _set_archived(db: DBSession):
            stmt = (
                update(SessionModel)
                .where(SessionModel.id == session_id)
                .values(time_archived=time)
                .returning(SessionModel)
            )
            row = db.execute(stmt).scalar_one_or_none()
            if not row:
                raise NotFoundError(f"Session not found: {session_id}")
            
            info = from_row(row)
            Database.effect(lambda: Bus.publish(SessionEvents.Updated, {"info": info.model_dump()}))
            return info
        
        result = Database.use(_set_archived)
        Database.execute_effects()
        return result
    
    def set_permission(self, session_id: str, permission: List[Dict]) -> SessionInfo:
        """Set session permission ruleset."""
        now = int(datetime.now().timestamp() * 1000)
        
        def _set_permission(db: DBSession):
            stmt = (
                update(SessionModel)
                .where(SessionModel.id == session_id)
                .values(permission=permission, time_updated=now)
                .returning(SessionModel)
            )
            row = db.execute(stmt).scalar_one_or_none()
            if not row:
                raise NotFoundError(f"Session not found: {session_id}")
            
            info = from_row(row)
            Database.effect(lambda: Bus.publish(SessionEvents.Updated, {"info": info.model_dump()}))
            return info
        
        result = Database.use(_set_permission)
        Database.execute_effects()
        return result
    
    def set_revert(
        self,
        session_id: str,
        revert: Optional[dict],
        summary: Optional[dict],
    ) -> SessionInfo:
        """Set session revert info."""
        now = int(datetime.now().timestamp() * 1000)
        
        def _set_revert(db: DBSession):
            values = {
                "revert": revert,
                "time_updated": now,
            }
            if summary:
                values["summary_additions"] = summary.get("additions")
                values["summary_deletions"] = summary.get("deletions")
                values["summary_files"] = summary.get("files")
            
            stmt = (
                update(SessionModel)
                .where(SessionModel.id == session_id)
                .values(**values)
                .returning(SessionModel)
            )
            row = db.execute(stmt).scalar_one_or_none()
            if not row:
                raise NotFoundError(f"Session not found: {session_id}")
            
            info = from_row(row)
            Database.effect(lambda: Bus.publish(SessionEvents.Updated, {"info": info.model_dump()}))
            return info
        
        result = Database.use(_set_revert)
        Database.execute_effects()
        return result
    
    def clear_revert(self, session_id: str) -> SessionInfo:
        """Clear session revert info."""
        now = int(datetime.now().timestamp() * 1000)
        
        def _clear_revert(db: DBSession):
            stmt = (
                update(SessionModel)
                .where(SessionModel.id == session_id)
                .values(revert=None, time_updated=now)
                .returning(SessionModel)
            )
            row = db.execute(stmt).scalar_one_or_none()
            if not row:
                raise NotFoundError(f"Session not found: {session_id}")
            
            info = from_row(row)
            Database.effect(lambda: Bus.publish(SessionEvents.Updated, {"info": info.model_dump()}))
            return info
        
        result = Database.use(_clear_revert)
        Database.execute_effects()
        return result
    
    def list(
        self,
        directory: Optional[str] = None,
        roots: bool = False,
        start: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 100,
    ) -> Iterator[SessionInfo]:
        """List sessions with optional filters."""
        def _list(db: DBSession):
            conditions = [SessionModel.project_id == self.project_id]
            
            if directory:
                conditions.append(SessionModel.directory == directory)
            if roots:
                conditions.append(SessionModel.parent_id.is_(None))
            if start:
                conditions.append(SessionModel.time_updated >= start)
            if search:
                conditions.append(SessionModel.title.like(f"%{search}%"))
            
            stmt = (
                select(SessionModel)
                .where(and_(*conditions))
                .order_by(desc(SessionModel.time_updated))
                .limit(limit)
            )
            
            rows = db.execute(stmt).scalars().all()
            for row in rows:
                yield from_row(row)
        
        yield from Database.use(_list)
    
    def children(self, parent_id: str) -> List[SessionInfo]:
        """Get child sessions of a parent session."""
        def _children(db: DBSession):
            stmt = select(SessionModel).where(
                and_(
                    SessionModel.project_id == self.project_id,
                    SessionModel.parent_id == parent_id,
                )
            )
            rows = db.execute(stmt).scalars().all()
            return [from_row(row) for row in rows]
        
        return Database.use(_children)
    
    def delete(self, session_id: str) -> None:
        """Delete a session and all its children."""
        session = self.get(session_id)
        if not session:
            return
        
        # Delete children first
        for child in self.children(session_id):
            self.delete(child.id)
        
        # Unshare
        try:
            self.unshare(session_id)
        except Exception:
            pass
        
        def _delete(db: DBSession):
            # CASCADE delete handles messages and parts automatically
            stmt = delete(SessionModel).where(SessionModel.id == session_id)
            db.execute(stmt)
            
            Database.effect(lambda: Bus.publish(
                SessionEvents.Deleted,
                {"info": session.model_dump()},
            ))
        
        Database.use(_delete)
        Database.execute_effects()
    
    def share(self, session_id: str) -> dict:
        """Share a session (placeholder)."""
        # This would integrate with a sharing service
        # For now, return a mock share URL
        share_url = f"https://opencode.example.com/share/{session_id}"
        
        def _share(db: DBSession):
            stmt = (
                update(SessionModel)
                .where(SessionModel.id == session_id)
                .values(share_url=share_url)
                .returning(SessionModel)
            )
            row = db.execute(stmt).scalar_one_or_none()
            if not row:
                raise NotFoundError(f"Session not found: {session_id}")
            
            info = from_row(row)
            Database.effect(lambda: Bus.publish(SessionEvents.Updated, {"info": info.model_dump()}))
            return {"url": share_url}
        
        result = Database.use(_share)
        Database.execute_effects()
        return result
    
    def unshare(self, session_id: str) -> None:
        """Unshare a session (placeholder)."""
        def _unshare(db: DBSession):
            stmt = (
                update(SessionModel)
                .where(SessionModel.id == session_id)
                .values(share_url=None)
                .returning(SessionModel)
            )
            row = db.execute(stmt).scalar_one_or_none()
            if not row:
                raise NotFoundError(f"Session not found: {session_id}")
            
            info = from_row(row)
            Database.effect(lambda: Bus.publish(SessionEvents.Updated, {"info": info.model_dump()}))
        
        Database.use(_unshare)
        Database.execute_effects()
    
    # Message operations
    
    def update_message(self, info: dict) -> dict:
        """Create or update a message."""
        session_id = info.get("sessionID")
        message_id = info.get("id")
        
        now = int(datetime.now().timestamp() * 1000)
        time_created = info.get("time", {}).get("created", now)
        
        # Remove id and sessionID from data
        data = {k: v for k, v in info.items() if k not in ["id", "sessionID"]}
        
        def _update_message(db: DBSession):
            # Check if exists
            stmt = select(MessageModel).where(MessageModel.id == message_id)
            existing = db.execute(stmt).scalar_one_or_none()
            
            if existing:
                # Update
                stmt = (
                    update(MessageModel)
                    .where(MessageModel.id == message_id)
                    .values(data=data)
                    .returning(MessageModel)
                )
                db.execute(stmt)
            else:
                # Insert
                row = MessageModel(
                    id=message_id,
                    session_id=session_id,
                    time_created=time_created,
                    data=data,
                )
                db.add(row)
            
            db.flush()
            
            Database.effect(lambda: Bus.publish(
                MessageEvents.Updated,
                {"info": info},
            ))
            
            return info
        
        Database.use(_update_message)
        Database.execute_effects()
        return info
    
    def remove_message(self, session_id: str, message_id: str) -> str:
        """Remove a message (CASCADE deletes parts)."""
        def _remove_message(db: DBSession):
            stmt = delete(MessageModel).where(MessageModel.id == message_id)
            db.execute(stmt)
            
            Database.effect(lambda: Bus.publish(
                MessageEvents.Removed,
                {"sessionID": session_id, "messageID": message_id},
            ))
        
        Database.use(_remove_message)
        Database.execute_effects()
        return message_id
    
    def update_part(self, part: dict) -> dict:
        """Create or update a part."""
        part_id = part.get("id")
        message_id = part.get("messageID")
        session_id = part.get("sessionID")
        
        now = int(datetime.now().timestamp() * 1000)
        
        # Remove id, messageID, sessionID from data
        data = {k: v for k, v in part.items() if k not in ["id", "messageID", "sessionID"]}
        
        def _update_part(db: DBSession):
            # Check if exists
            stmt = select(PartModel).where(PartModel.id == part_id)
            existing = db.execute(stmt).scalar_one_or_none()
            
            if existing:
                # Update
                stmt = (
                    update(PartModel)
                    .where(PartModel.id == part_id)
                    .values(data=data)
                    .returning(PartModel)
                )
                db.execute(stmt)
            else:
                # Insert
                row = PartModel(
                    id=part_id,
                    message_id=message_id,
                    session_id=session_id,
                    time_created=now,
                    data=data,
                )
                db.add(row)
            
            db.flush()
            
            Database.effect(lambda: Bus.publish(
                MessageEvents.PartUpdated,
                {"part": part},
            ))
            
            return part
        
        Database.use(_update_part)
        Database.execute_effects()
        return part
    
    def remove_part(self, session_id: str, message_id: str, part_id: str) -> str:
        """Remove a part."""
        def _remove_part(db: DBSession):
            stmt = delete(PartModel).where(PartModel.id == part_id)
            db.execute(stmt)
            
            Database.effect(lambda: Bus.publish(
                MessageEvents.PartRemoved,
                {"sessionID": session_id, "messageID": message_id, "partID": part_id},
            ))
        
        Database.use(_remove_part)
        Database.execute_effects()
        return part_id
    
    def list_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict]:
        """List messages for a session."""
        def _list_messages(db: DBSession):
            # Get messages
            stmt = (
                select(MessageModel)
                .where(MessageModel.session_id == session_id)
                .order_by(desc(MessageModel.time_created))
            )
            if limit:
                stmt = stmt.limit(limit)
            
            messages = db.execute(stmt).scalars().all()
            result = []
            
            for msg in messages:
                info = {**msg.data, "id": msg.id, "sessionID": msg.session_id}
                
                # Get parts
                parts_stmt = select(PartModel).where(PartModel.message_id == msg.id)
                parts = db.execute(parts_stmt).scalars().all()
                parts_data = [
                    {**p.data, "id": p.id, "sessionID": p.session_id, "messageID": p.message_id}
                    for p in parts
                ]
                
                result.append({"info": info, "parts": parts_data})
            
            return result
        
        return Database.use(_list_messages)
    
    def get_message(self, session_id: str, message_id: str) -> Optional[dict]:
        """Get a single message with parts."""
        def _get_message(db: DBSession):
            stmt = select(MessageModel).where(MessageModel.id == message_id)
            msg = db.execute(stmt).scalar_one_or_none()
            
            if not msg:
                return None
            
            info = {**msg.data, "id": msg.id, "sessionID": msg.session_id}
            
            parts_stmt = select(PartModel).where(PartModel.message_id == message_id)
            parts = db.execute(parts_stmt).scalars().all()
            parts_data = [
                {**p.data, "id": p.id, "sessionID": p.session_id, "messageID": p.message_id}
                for p in parts
            ]
            
            return {"info": info, "parts": parts_data}
        
        return Database.use(_get_message)
    
    # Token usage calculation
    
    @staticmethod
    def calculate_usage(
        model: dict,
        usage: dict,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Calculate token usage and cost."""
        def safe(value):
            if value is None or not isinstance(value, (int, float)):
                return 0
            if not float('-inf') < value < float('inf'):
                return 0
            return value
        
        input_tokens = safe(usage.get("inputTokens", 0))
        output_tokens = safe(usage.get("outputTokens", 0))
        reasoning_tokens = safe(usage.get("reasoningTokens", 0))
        
        cache_read = safe(usage.get("cachedInputTokens", 0))
        cache_write = safe(
            (metadata or {}).get("anthropic", {}).get("cacheCreationInputTokens", 0) or
            (metadata or {}).get("bedrock", {}).get("usage", {}).get("cacheWriteInputTokens", 0) or
            (metadata or {}).get("venice", {}).get("usage", {}).get("cacheCreationInputTokens", 0) or
            0
        )
        
        # Anthropic doesn't include cached tokens in inputTokens
        excludes_cached = bool(
            (metadata or {}).get("anthropic") or
            (metadata or {}).get("bedrock")
        )
        
        adjusted_input = safe(input_tokens) if excludes_cached else safe(
            input_tokens - cache_read - cache_write
        )
        
        # Calculate total
        if model.get("api", {}).get("npm") in [
            "@ai-sdk/anthropic",
            "@ai-sdk/amazon-bedrock",
            "@ai-sdk/google-vertex/anthropic",
        ]:
            total = adjusted_input + output_tokens + cache_read + cache_write
        else:
            total = safe(usage.get("totalTokens", 0))
        
        tokens = {
            "total": total,
            "input": adjusted_input,
            "output": output_tokens,
            "reasoning": reasoning_tokens,
            "cache": {
                "write": cache_write,
                "read": cache_read,
            },
        }
        
        # Calculate cost
        cost_info = model.get("cost", {})
        if tokens["input"] + tokens["cache"]["read"] > 200_000:
            cost_info = model.get("cost", {}).get("experimentalOver200K", cost_info)
        
        cost = safe(
            Decimal(0)
            + Decimal(tokens["input"]) * Decimal(cost_info.get("input", 0)) / Decimal(1_000_000)
            + Decimal(tokens["output"]) * Decimal(cost_info.get("output", 0)) / Decimal(1_000_000)
            + Decimal(tokens["cache"]["read"]) * Decimal(cost_info.get("cache", {}).get("read", 0)) / Decimal(1_000_000)
            + Decimal(tokens["cache"]["write"]) * Decimal(cost_info.get("cache", {}).get("write", 0)) / Decimal(1_000_000)
            + Decimal(tokens["reasoning"]) * Decimal(cost_info.get("output", 0)) / Decimal(1_000_000)
        )
        
        return {
            "cost": float(cost),
            "tokens": tokens,
        }


# Message events
class MessageEvents:
    """Message bus events."""
    
    Updated = BusEvent.define("message.updated", {"info": dict})
    Removed = BusEvent.define("message.removed", {"sessionID": str, "messageID": str})
    PartUpdated = BusEvent.define("message.part.updated", {"part": dict})
    PartDelta = BusEvent.define("message.part.delta", {
        "sessionID": str,
        "messageID": str,
        "partID": str,
        "field": str,
        "delta": str,
    })
    PartRemoved = BusEvent.define("message.part.removed", {
        "sessionID": str,
        "messageID": str,
        "partID": str,
    })


# Module-level convenience functions
_manager: Optional[SessionManager] = None


def get_manager(project_id: str, directory: str) -> SessionManager:
    """Get or create the session manager."""
    global _manager
    if _manager is None or _manager.project_id != project_id:
        _manager = SessionManager(project_id, directory)
    return _manager


def create_session(
    project_id: str,
    directory: str,
    parent_id: Optional[str] = None,
    title: Optional[str] = None,
    permission: Optional[List[Dict]] = None,
) -> SessionInfo:
    """Create a new session."""
    manager = get_manager(project_id, directory)
    return manager.create(parent_id=parent_id, title=title, permission=permission)


def get_session(project_id: str, directory: str, session_id: str) -> Optional[SessionInfo]:
    """Get a session by ID."""
    manager = get_manager(project_id, directory)
    return manager.get(session_id)
