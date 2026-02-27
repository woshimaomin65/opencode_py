"""Permission module for OpenCode."""

from opencode.permission.permission import (
    PermissionManager,
    PermissionLevel,
    PermissionRule,
    get_permission_manager,
)

__all__ = [
    "PermissionManager",
    "PermissionLevel",
    "PermissionRule",
    "get_permission_manager",
]
