"""Shell module for OpenCode."""

from .shell import (
    ProcessStatus,
    ProcessResult,
    ProcessInfo,
    ShellExecutor,
    run_command,
    run_command_stream,
    which,
    check_command,
    bash,
    sh,
)

__all__ = [
    "ProcessStatus",
    "ProcessResult",
    "ProcessInfo",
    "ShellExecutor",
    "run_command",
    "run_command_stream",
    "which",
    "check_command",
    "bash",
    "sh",
]
