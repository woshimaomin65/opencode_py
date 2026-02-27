"""
Bash tool for OpenCode.

Executes shell commands with proper timeout, permission handling,
and output management.
"""

import asyncio
import os
import signal
import psutil
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass

from tool.tool import BaseTool, ToolDefinition, ToolParameter, ToolResult, ToolStatus, ToolContext


# Configuration constants
MAX_METADATA_LENGTH = 30_000
DEFAULT_TIMEOUT_MS = 2 * 60 * 1000  # 2 minutes


@dataclass
class BashToolConfig:
    """Configuration for BashTool."""
    allowed_commands: Optional[list[str]] = None
    working_dir: Optional[Path] = None
    default_timeout_ms: int = DEFAULT_TIMEOUT_MS


class BashTool(BaseTool):
    """Tool for executing shell commands."""
    
    def __init__(self, config: Optional[BashToolConfig] = None):
        self.config = config or BashToolConfig()
        self.working_dir = self.config.working_dir or Path.cwd()
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="bash",
            description="Execute a shell command in the current directory",
            parameters=[
                ToolParameter(
                    name="command",
                    type="string",
                    description="The command to execute",
                    required=True,
                ),
                ToolParameter(
                    name="timeout",
                    type="number",
                    description="Optional timeout in milliseconds",
                    required=False,
                ),
                ToolParameter(
                    name="workdir",
                    type="string",
                    description=f"The working directory to run the command in. Defaults to {self.working_dir}. Use this instead of 'cd' commands.",
                    required=False,
                ),
                ToolParameter(
                    name="description",
                    type="string",
                    description="Clear, concise description of what this command does in 5-10 words",
                    required=True,
                ),
            ],
        )
    
    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        command = kwargs.get("command")
        timeout_ms = kwargs.get("timeout", self.config.default_timeout_ms)
        workdir = kwargs.get("workdir", str(self.working_dir))
        description = kwargs.get("description", "Execute shell command")
        
        # Validate parameters
        if not command:
            return ToolResult(
                tool_name="bash",
                status=ToolStatus.ERROR,
                content=None,
                error="Missing required parameter: command",
            )
        
        if timeout_ms is not None and timeout_ms < 0:
            return ToolResult(
                tool_name="bash",
                status=ToolStatus.ERROR,
                content=None,
                error=f"Invalid timeout value: {timeout_ms}. Timeout must be a positive number.",
            )
        
        timeout = timeout_ms / 1000.0  # Convert to seconds
        
        try:
            work_dir = Path(workdir)
            if not work_dir.is_absolute():
                work_dir = self.working_dir / work_dir
            
            # Request permission
            await ctx.ask(
                permission="bash",
                patterns=[command],
                always=["*"],
                metadata={"command": command, "workdir": str(work_dir)},
            )
            
            # Initialize metadata
            ctx.metadata({
                "metadata": {
                    "output": "",
                    "description": description,
                }
            })
            
            output = ""
            timed_out = False
            aborted = False
            exited = False
            
            # Create subprocess
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
                env=os.environ,
                preexec_fn=os.setsid if os.name != 'nt' else None,
            )
            
            async def append_output(chunk: bytes) -> None:
                nonlocal output
                output += chunk.decode('utf-8', errors='replace')
                # Truncate metadata to avoid giant blobs
                metadata_output = output
                if len(metadata_output) > MAX_METADATA_LENGTH:
                    metadata_output = metadata_output[:MAX_METADATA_LENGTH] + "\n\n..."
                ctx.metadata({
                    "metadata": {
                        "output": metadata_output,
                        "description": description,
                    }
                })
            
            async def read_stream(stream, callback):
                while True:
                    chunk = await stream.read(4096)
                    if not chunk:
                        break
                    await callback(chunk)
            
            # Start reading output
            stdout_task = asyncio.create_task(read_stream(process.stdout, append_output))
            stderr_task = asyncio.create_task(read_stream(process.stderr, append_output))
            
            # Wait for process with timeout
            try:
                await asyncio.wait_for(process.wait(), timeout=timeout)
                exited = True
            except asyncio.TimeoutError:
                timed_out = True
                # Kill the process tree
                self._kill_process_tree(process)
                exited = True
            
            # Wait for output reading to complete
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
            
            # Check for abort
            if ctx.aborted:
                aborted = True
                if not exited:
                    self._kill_process_tree(process)
            
            # Build result metadata
            result_metadata = []
            if timed_out:
                result_metadata.append(f"bash tool terminated command after exceeding timeout {timeout_ms} ms")
            if aborted:
                result_metadata.append("User aborted the command")
            
            if result_metadata:
                output += "\n\n<bash_metadata>\n" + "\n".join(result_metadata) + "\n</bash_metadata>"
            
            # Truncate output if too long
            if len(output) > MAX_METADATA_LENGTH:
                output = output[:MAX_METADATA_LENGTH] + "\n\n..."
            
            status = ToolStatus.SUCCESS if process.returncode == 0 else ToolStatus.ERROR
            
            return ToolResult(
                tool_name="bash",
                status=status,
                content={
                    "stdout": output,
                    "stderr": "",
                    "exit_code": process.returncode,
                },
                error=output if process.returncode != 0 else None,
                title=description,
                metadata={
                    "output": output,
                    "exit": process.returncode,
                    "description": description,
                },
            )
            
        except Exception as e:
            return ToolResult(
                tool_name="bash",
                status=ToolStatus.ERROR,
                content=None,
                error=str(e),
            )
    
    def _kill_process_tree(self, process: asyncio.subprocess.Process) -> None:
        """Kill a process and all its children."""
        try:
            if os.name != 'nt':
                # On Unix, kill the process group
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            else:
                # On Windows, use taskkill
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    capture_output=True,
                )
        except Exception:
            pass
        
        # Also try using psutil for more thorough cleanup
        try:
            parent = psutil.Process(process.pid)
            for child in parent.children(recursive=True):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            parent.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
