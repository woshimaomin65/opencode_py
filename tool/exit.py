"""
Exit tool for OpenCode.

Provides functionality to:
- End the current session
- Signal task completion
- Exit with status
"""

from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass
from enum import Enum

from opencode.tool.tool import BaseTool, ToolDefinition, ToolParameter, ToolResult, ToolStatus, ToolContext


class ExitStatus(str, Enum):
    """Exit status for the session."""
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class ExitToolConfig:
    """Configuration for ExitTool."""
    working_dir: Optional[Path] = None


class ExitTool(BaseTool):
    """Tool for exiting the current session."""
    
    def __init__(self, config: Optional[ExitToolConfig] = None):
        self.config = config or ExitToolConfig()
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="exit",
            description="End the current session and optionally provide a summary",
            parameters=[
                ToolParameter(
                    name="status",
                    type="string",
                    description="Exit status: 'success', 'error', or 'cancelled'",
                    required=False,
                    enum=["success", "error", "cancelled"],
                    default="success",
                ),
                ToolParameter(
                    name="message",
                    type="string",
                    description="Optional message to display on exit",
                    required=False,
                ),
                ToolParameter(
                    name="summary",
                    type="string",
                    description="Optional summary of what was accomplished",
                    required=False,
                ),
            ],
        )
    
    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        status = kwargs.get("status", "success")
        message = kwargs.get("message")
        summary = kwargs.get("summary")
        
        try:
            # Request permission
            await ctx.ask(
                permission="exit",
                patterns=["*"],
                always=["*"],
                metadata={
                    "status": status,
                    "message": message,
                    "summary": summary,
                },
            )
            
            # Build output
            output_parts = []
            
            if message:
                output_parts.append(message)
            
            if summary:
                output_parts.append(f"\n## Summary\n{summary}")
            
            output_parts.append(f"\n\nSession ended with status: {status}")
            
            output = "\n".join(output_parts)
            
            return ToolResult(
                tool_name="exit",
                status=ToolStatus.SUCCESS,
                content=output,
                title="Session exit",
                metadata={
                    "status": status,
                    "message": message,
                    "summary": summary,
                },
            )
            
        except Exception as e:
            return ToolResult(
                tool_name="exit",
                status=ToolStatus.ERROR,
                content=None,
                error=str(e),
            )


class PlanEnterTool(BaseTool):
    """Tool for entering plan mode."""
    
    def __init__(self, config: Optional[ExitToolConfig] = None):
        self.config = config or ExitToolConfig()
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="plan_enter",
            description="Enter planning mode to outline a solution before implementation",
            parameters=[
                ToolParameter(
                    name="goal",
                    type="string",
                    description="The goal or task to plan for",
                    required=True,
                ),
                ToolParameter(
                    name="constraints",
                    type="string",
                    description="Any constraints or requirements",
                    required=False,
                ),
            ],
        )
    
    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        goal = kwargs.get("goal")
        constraints = kwargs.get("constraints")
        
        if not goal:
            return ToolResult(
                tool_name="plan_enter",
                status=ToolStatus.ERROR,
                content=None,
                error="Missing required parameter: goal",
            )
        
        try:
            await ctx.ask(
                permission="plan_enter",
                patterns=["*"],
                always=["*"],
                metadata={
                    "goal": goal,
                    "constraints": constraints,
                },
            )
            
            output = f"Entering plan mode for: {goal}"
            if constraints:
                output += f"\n\nConstraints: {constraints}"
            
            output += "\n\nPlease outline your plan before proceeding with implementation."
            
            return ToolResult(
                tool_name="plan_enter",
                status=ToolStatus.SUCCESS,
                content=output,
                title="Plan mode entered",
                metadata={
                    "goal": goal,
                    "constraints": constraints,
                },
            )
            
        except Exception as e:
            return ToolResult(
                tool_name="plan_enter",
                status=ToolStatus.ERROR,
                content=None,
                error=str(e),
            )


class PlanExitTool(BaseTool):
    """Tool for exiting plan mode."""
    
    def __init__(self, config: Optional[ExitToolConfig] = None):
        self.config = config or ExitToolConfig()
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="plan_exit",
            description="Exit planning mode and proceed with implementation",
            parameters=[
                ToolParameter(
                    name="plan",
                    type="string",
                    description="The final plan to implement",
                    required=True,
                ),
                ToolParameter(
                    name="ready",
                    type="boolean",
                    description="Whether ready to proceed with implementation",
                    required=False,
                    default=True,
                ),
            ],
        )
    
    async def execute(self, ctx: ToolContext, **kwargs) -> ToolResult:
        plan = kwargs.get("plan")
        ready = kwargs.get("ready", True)
        
        if not plan:
            return ToolResult(
                tool_name="plan_exit",
                status=ToolStatus.ERROR,
                content=None,
                error="Missing required parameter: plan",
            )
        
        try:
            await ctx.ask(
                permission="plan_exit",
                patterns=["*"],
                always=["*"],
                metadata={
                    "plan": plan,
                    "ready": ready,
                },
            )
            
            output = "Exiting plan mode."
            if ready:
                output += "\n\nProceeding with implementation based on the following plan:\n\n"
                output += plan
            else:
                output += "\n\nPlan saved but not proceeding with implementation yet."
            
            return ToolResult(
                tool_name="plan_exit",
                status=ToolStatus.SUCCESS,
                content=output,
                title="Plan mode exited",
                metadata={
                    "plan": plan,
                    "ready": ready,
                },
            )
            
        except Exception as e:
            return ToolResult(
                tool_name="plan_exit",
                status=ToolStatus.ERROR,
                content=None,
                error=str(e),
            )
