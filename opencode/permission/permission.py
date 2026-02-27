"""
Permission module for OpenCode.

Handles permission management for tool execution:
- Auto-approve permissions
- Ask-before-execute permissions
- Denied permissions
- Permission persistence
"""

import json
from enum import Enum
from pathlib import Path
from typing import Optional, Set
from dataclasses import dataclass, field
from datetime import datetime


class PermissionLevel(Enum):
    """Permission levels."""
    ALLOW = "allow"      # Always allow without asking
    ASK = "ask"          # Ask before executing
    DENY = "deny"        # Always deny


@dataclass
class PermissionRule:
    """A permission rule."""
    tool: str
    level: PermissionLevel
    pattern: Optional[str] = None  # Pattern to match (e.g., file path pattern)
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def matches(self, tool: str, context: Optional[dict] = None) -> bool:
        """Check if this rule matches the given tool and context."""
        if self.tool != tool:
            return False
        
        if self.expires_at and datetime.now() > self.expires_at:
            return False
        
        if self.pattern and context:
            # Simple pattern matching for file paths
            import fnmatch
            path = context.get("path", "")
            if not fnmatch.fnmatch(path, self.pattern):
                return False
        
        return True
    
    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "level": self.level.value,
            "pattern": self.pattern,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PermissionRule":
        return cls(
            tool=data["tool"],
            level=PermissionLevel(data["level"]),
            pattern=data.get("pattern"),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
        )


class PermissionManager:
    """
    Manager for tool execution permissions.
    
    Supports:
    - Default permissions per tool
    - Pattern-based permissions (e.g., allow write to specific directories)
    - Temporary permissions (session-only or time-limited)
    - Persistent permissions (saved to disk)
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path.cwd() / ".opencode" / "permissions.json"
        self._rules: list[PermissionRule] = []
        self._session_rules: list[PermissionRule] = []  # Temporary rules for this session
        self._load()
    
    def _load(self) -> None:
        """Load permissions from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                self._rules = [PermissionRule.from_dict(r) for r in data.get("rules", [])]
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Failed to load permissions: {e}")
                self._rules = []
        else:
            # Set up default permissions
            self._setup_defaults()
    
    def _setup_defaults(self) -> None:
        """Set up default permissions."""
        # Read and search are always allowed
        self._rules.append(PermissionRule(
            tool="read",
            level=PermissionLevel.ALLOW,
        ))
        self._rules.append(PermissionRule(
            tool="search",
            level=PermissionLevel.ALLOW,
        ))
        
        # Write requires asking by default
        self._rules.append(PermissionRule(
            tool="write",
            level=PermissionLevel.ASK,
        ))
        
        # Edit requires asking by default
        self._rules.append(PermissionRule(
            tool="edit",
            level=PermissionLevel.ASK,
        ))
        
        # Shell commands require asking by default
        self._rules.append(PermissionRule(
            tool="shell",
            level=PermissionLevel.ASK,
        ))
    
    def _save(self) -> None:
        """Save permissions to disk."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "rules": [r.to_dict() for r in self._rules],
        }
        
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def check_permission(
        self,
        tool: str,
        context: Optional[dict] = None,
    ) -> PermissionLevel:
        """
        Check permission for a tool execution.
        
        Returns the permission level (ALLOW, ASK, or DENY).
        """
        # Check session rules first (most specific)
        for rule in reversed(self._session_rules):
            if rule.matches(tool, context):
                return rule.level
        
        # Check persistent rules
        for rule in reversed(self._rules):
            if rule.matches(tool, context):
                return rule.level
        
        # Default to ASK for unknown tools
        return PermissionLevel.ASK
    
    def add_rule(
        self,
        tool: str,
        level: PermissionLevel,
        pattern: Optional[str] = None,
        expires_in_seconds: Optional[int] = None,
        session_only: bool = False,
    ) -> PermissionRule:
        """Add a permission rule."""
        expires_at = None
        if expires_in_seconds:
            from datetime import timedelta
            expires_at = datetime.now() + timedelta(seconds=expires_in_seconds)
        
        rule = PermissionRule(
            tool=tool,
            level=level,
            pattern=pattern,
            expires_at=expires_at,
        )
        
        if session_only:
            self._session_rules.append(rule)
        else:
            self._rules.append(rule)
            self._save()
        
        return rule
    
    def allow(
        self,
        tool: str,
        pattern: Optional[str] = None,
        session_only: bool = False,
    ) -> PermissionRule:
        """Add an allow rule."""
        return self.add_rule(tool, PermissionLevel.ALLOW, pattern, session_only=session_only)
    
    def deny(
        self,
        tool: str,
        pattern: Optional[str] = None,
        session_only: bool = False,
    ) -> PermissionRule:
        """Add a deny rule."""
        return self.add_rule(tool, PermissionLevel.DENY, pattern, session_only=session_only)
    
    def remove_rules(
        self,
        tool: Optional[str] = None,
        pattern: Optional[str] = None,
    ) -> int:
        """Remove matching rules. Returns count of removed rules."""
        removed = 0
        
        # Remove from persistent rules
        new_rules = []
        for rule in self._rules:
            match = True
            if tool and rule.tool != tool:
                match = False
            if pattern and rule.pattern != pattern:
                match = False
            if match:
                removed += 1
            else:
                new_rules.append(rule)
        self._rules = new_rules
        
        # Remove from session rules
        new_session_rules = []
        for rule in self._session_rules:
            match = True
            if tool and rule.tool != tool:
                match = False
            if pattern and rule.pattern != pattern:
                match = False
            if match:
                removed += 1
            else:
                new_session_rules.append(rule)
        self._session_rules = new_session_rules
        
        if removed > 0:
            self._save()
        
        return removed
    
    def list_rules(self, include_session: bool = True) -> list[PermissionRule]:
        """List all permission rules."""
        rules = self._rules.copy()
        if include_session:
            rules.extend(self._session_rules)
        return rules
    
    def clear_session_rules(self) -> None:
        """Clear all session-only rules."""
        self._session_rules = []


# Global permission manager instance
_permission_manager: Optional[PermissionManager] = None


def get_permission_manager(storage_path: Optional[Path] = None) -> PermissionManager:
    """Get the global permission manager."""
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager(storage_path)
    return _permission_manager
