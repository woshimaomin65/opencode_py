"""
Shell module for OpenCode.

Handles shell command execution including:
- Command execution
- Process management
- Output streaming
- PTY support
"""

import asyncio
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional, AsyncIterator, Callable
from dataclasses import dataclass, field
from enum import Enum


class ProcessStatus(Enum):
    """Process status."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"


@dataclass
class ProcessResult:
    """Result from process execution."""
    command: str
    exit_code: int
    stdout: str
    stderr: str
    status: ProcessStatus
    duration: float
    cwd: Optional[Path] = None


@dataclass
class ProcessInfo:
    """Information about a running process."""
    pid: int
    command: str
    cwd: Path
    status: ProcessStatus
    start_time: float


class ShellExecutor:
    """
    Shell command executor with async support.
    """
    
    def __init__(
        self,
        cwd: Optional[Path] = None,
        env: Optional[dict[str, str]] = None,
        shell: str = "/bin/bash",
        timeout: float = 60.0,
    ):
        self.cwd = cwd or Path.cwd()
        self.env = env or os.environ.copy()
        self.shell = shell
        self.timeout = timeout
        self._processes: dict[int, asyncio.subprocess.Process] = {}
    
    async def execute(
        self,
        command: str,
        capture_output: bool = True,
        check: bool = False,
    ) -> ProcessResult:
        """
        Execute a shell command.
        
        Args:
            command: Command to execute
            capture_output: Whether to capture stdout/stderr
            check: Raise exception on non-zero exit code
            
        Returns:
            ProcessResult with execution details
        """
        import time
        start_time = time.time()
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE if capture_output else None,
                stderr=asyncio.subprocess.PIPE if capture_output else None,
                cwd=self.cwd,
                env=self.env,
                shell=True,
            )
            
            self._processes[process.pid] = process
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ProcessResult(
                    command=command,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Command timed out after {self.timeout}s",
                    status=ProcessStatus.KILLED,
                    duration=time.time() - start_time,
                    cwd=self.cwd,
                )
            
            finally:
                self._processes.pop(process.pid, None)
            
            stdout_str = stdout.decode('utf-8', errors='replace') if stdout else ""
            stderr_str = stderr.decode('utf-8', errors='replace') if stderr else ""
            
            status = ProcessStatus.COMPLETED if process.returncode == 0 else ProcessStatus.FAILED
            
            if check and process.returncode != 0:
                raise subprocess.CalledProcessError(
                    process.returncode,
                    command,
                    stdout_str,
                    stderr_str,
                )
            
            return ProcessResult(
                command=command,
                exit_code=process.returncode or 0,
                stdout=stdout_str,
                stderr=stderr_str,
                status=status,
                duration=time.time() - start_time,
                cwd=self.cwd,
            )
            
        except Exception as e:
            return ProcessResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                status=ProcessStatus.FAILED,
                duration=time.time() - start_time,
                cwd=self.cwd,
            )
    
    async def execute_stream(
        self,
        command: str,
        on_stdout: Optional[Callable[[str], None]] = None,
        on_stderr: Optional[Callable[[str], None]] = None,
    ) -> AsyncIterator[str]:
        """
        Execute a command and stream output.
        
        Args:
            command: Command to execute
            on_stdout: Callback for stdout
            on_stderr: Callback for stderr
            
        Yields:
            Output lines
        """
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd,
            env=self.env,
            shell=True,
        )
        
        self._processes[process.pid] = process
        
        try:
            # Read stdout and stderr concurrently
            async def read_stream(stream, callback, is_stderr=False):
                if stream:
                    async for line in stream:
                        decoded = line.decode('utf-8', errors='replace')
                        if callback:
                            callback(decoded)
                        yield decoded
            
            # Combine stdout and stderr
            stdout_lines = read_stream(process.stdout, on_stdout)
            stderr_lines = read_stream(process.stderr, on_stderr, is_stderr=True)
            
            async for line in stdout_lines:
                yield line
            
            async for line in stderr_lines:
                yield line
            
            await process.wait()
            
        finally:
            self._processes.pop(process.pid, None)
    
    async def kill(self, pid: int) -> bool:
        """Kill a running process."""
        process = self._processes.get(pid)
        if process:
            process.kill()
            await process.wait()
            return True
        return False
    
    async def kill_all(self) -> int:
        """Kill all running processes. Returns count of killed processes."""
        count = 0
        for pid in list(self._processes.keys()):
            if await self.kill(pid):
                count += 1
        return count
    
    def list_processes(self) -> list[ProcessInfo]:
        """List all running processes."""
        import time
        results = []
        for pid, process in self._processes.items():
            results.append(ProcessInfo(
                pid=pid,
                command=str(process.args),
                cwd=self.cwd,
                status=ProcessStatus.RUNNING,
                start_time=time.time(),
            ))
        return results


async def run_command(
    command: str,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
    timeout: float = 60.0,
) -> ProcessResult:
    """
    Run a shell command.
    
    Args:
        command: Command to run
        cwd: Working directory
        env: Environment variables
        timeout: Timeout in seconds
        
    Returns:
        ProcessResult
    """
    executor = ShellExecutor(cwd=cwd, env=env, timeout=timeout)
    return await executor.execute(command)


async def run_command_stream(
    command: str,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
) -> AsyncIterator[str]:
    """
    Run a command and stream output.
    
    Args:
        command: Command to run
        cwd: Working directory
        env: Environment variables
        
    Yields:
        Output lines
    """
    executor = ShellExecutor(cwd=cwd, env=env)
    async for output in executor.execute_stream(command):
        yield output


async def which(command: str) -> Optional[Path]:
    """
    Find the path of a command.
    
    Args:
        command: Command name
        
    Returns:
        Path to command or None if not found
    """
    return shutil.which(command)


async def check_command(command: str) -> bool:
    """
    Check if a command is available.
    
    Args:
        command: Command name
        
    Returns:
        True if available, False otherwise
    """
    path = await which(command)
    return path is not None


# Convenience functions
async def bash(command: str, **kwargs) -> ProcessResult:
    """Run a bash command."""
    return await run_command(command, **kwargs)


async def sh(command: str, **kwargs) -> ProcessResult:
    """Run a sh command."""
    return await run_command(command, shell="/bin/sh", **kwargs)


# Import for which function
import shutil
