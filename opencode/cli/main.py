"""
CLI module for OpenCode.

Command-line interface for interacting with the AI assistant.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.live import Live
from rich.spinner import Spinner

from ..config import Config
from ..tool import init_default_tools, ToolRegistry
from ..agent import Agent
from ..session import SessionManager


console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="opencode")
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, dir_okay=False),
    help="Path to configuration file",
)
@click.option(
    "--project", "-p",
    type=click.Path(exists=True, file_okay=False),
    help="Project root directory",
)
@click.pass_context
def main(ctx, config: Optional[str], project: Optional[str]):
    """OpenCode - AI-powered coding assistant"""
    ctx.ensure_object(dict)
    
    project_path = Path(project) if project else Path.cwd()
    ctx.obj["project_path"] = project_path
    
    # Load configuration
    ctx.obj["config"] = Config(project_root=project_path).load()
    
    # Initialize tools
    init_default_tools(working_dir=project_path)


@main.command()
@click.argument("prompt", nargs=-1, required=False)
@click.option(
    "--model", "-m",
    default="claude-sonnet-4-20250514",
    help="Model to use",
)
@click.option(
    "--provider", "-p",
    default="anthropic",
    help="Provider to use (anthropic, openai, google)",
)
@click.option(
    "--session", "-s",
    help="Session ID to continue",
)
@click.option(
    "--system-prompt",
    help="System prompt to use",
)
@click.option(
    "--no-stream",
    is_flag=True,
    help="Disable streaming output",
)
@click.pass_context
def run(ctx, prompt, model, provider, session, system_prompt, no_stream):
    """Run a single prompt and exit"""
    project_path = ctx.obj["project_path"]
    config = ctx.obj["config"]
    
    # Get prompt from args or stdin
    if not prompt:
        if sys.stdin.isatty():
            console.print("[red]Error: No prompt provided[/red]")
            console.print("Usage: opencode run <your prompt>")
            console.print("   or: echo 'your prompt' | opencode run")
            sys.exit(1)
        prompt_text = sys.stdin.read().strip()
    else:
        prompt_text = " ".join(prompt)
    
    if not prompt_text:
        console.print("[red]Error: Empty prompt[/red]")
        sys.exit(1)
    
    # Get system prompt from config or argument
    sys_prompt = system_prompt or config.custom_instructions
    
    # Create agent
    agent = Agent.create(
        model=model,
        provider=provider,
        system_prompt=sys_prompt,
        tools=["read", "write", "edit", "bash", "search"],
        working_dir=project_path,
    )
    
    # Load existing session if specified
    if session:
        loaded_session = SessionManager().get_session(session)
        if loaded_session:
            agent.session = loaded_session
            console.print(f"[green]Loaded session: {session}[/green]")
    
    async def run_agent():
        if no_stream:
            with console.status("[bold green]Thinking...", spinner="dots"):
                response = await agent.run(prompt_text)
            console.print()
            console.print(Markdown(response))
        else:
            console.print()
            console.print(Panel(f"[bold blue]User:[/bold blue] {prompt_text}", border_style="blue"))
            console.print()
            console.print("[bold green]Assistant:[/bold green] ", end="")
            
            response = ""
            async for token in agent.run_stream(prompt_text):
                response += token
                console.print(token, end="")
            
            console.print()
        
        # Print token usage
        usage = agent.token_usage
        console.print()
        console.print(f"[dim]Tokens: {usage['input_tokens']} input, {usage['output_tokens']} output, {usage['total_tokens']} total[/dim]")
        
        # Save session
        session_path = agent.save_session()
        console.print(f"[dim]Session saved: {session_path}[/dim]")
        console.print(f"[dim]Session ID: {agent.session.id}[/dim]")
    
    asyncio.run(run_agent())


@main.command()
@click.option(
    "--model", "-m",
    default="claude-sonnet-4-20250514",
    help="Model to use",
)
@click.option(
    "--provider", "-p",
    default="anthropic",
    help="Provider to use",
)
@click.option(
    "--session", "-s",
    help="Session ID to continue",
)
@click.pass_context
def interactive(ctx, model, provider, session):
    """Start interactive chat mode"""
    project_path = ctx.obj["project_path"]
    config = ctx.obj["config"]
    
    # Create agent
    agent = Agent.create(
        model=model,
        provider=provider,
        system_prompt=config.custom_instructions,
        tools=["read", "write", "edit", "bash", "search"],
        working_dir=project_path,
    )
    
    # Load existing session if specified
    if session:
        loaded_session = SessionManager().get_session(session)
        if loaded_session:
            agent.session = loaded_session
            console.print(f"[green]Loaded session: {session}[/green]")
    
    console.print()
    console.print(Panel("[bold]OpenCode Interactive Mode[/bold]\nType 'quit' or 'exit' to end\nType 'clear' to clear conversation\nType 'session' to show session info", border_style="green"))
    console.print()
    
    async def chat():
        while True:
            try:
                prompt = click.prompt(click.style("You", bold=True, fg="blue"), prompt_suffix="> ")
            except (EOFError, KeyboardInterrupt):
                console.print()
                console.print("[yellow]Goodbye![/yellow]")
                break
            
            prompt = prompt.strip()
            
            if not prompt:
                continue
            
            if prompt.lower() in ("quit", "exit"):
                console.print("[yellow]Goodbye![/yellow]")
                break
            
            if prompt.lower() == "clear":
                agent.reset()
                console.print("[green]Conversation cleared[/green]")
                continue
            
            if prompt.lower() == "session":
                console.print(f"Session ID: {agent.session.id}")
                console.print(f"Messages: {len(agent.session.messages)}")
                console.print(f"Tokens: {agent.token_usage['total_tokens']}")
                continue
            
            console.print()
            
            try:
                response = ""
                async for token in agent.run_stream(prompt):
                    response += token
                    console.print(token, end="")
                console.print()
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
            
            console.print()
        
        # Save session
        session_path = agent.save_session()
        console.print(f"[dim]Session saved: {session_path}[/dim]")
    
    asyncio.run(chat())


@main.command()
@click.option(
    "--session-id",
    help="Filter by session ID",
)
@click.pass_context
def sessions(ctx, session_id):
    """List or manage sessions"""
    manager = SessionManager()
    
    if session_id:
        # Show specific session
        session = manager.get_session(session_id)
        if session:
            console.print(f"[bold]Session: {session_id}[/bold]")
            console.print(f"Model: {session.model}")
            console.print(f"Provider: {session.provider}")
            console.print(f"Created: {session.created_at}")
            console.print(f"Messages: {len(session.messages)}")
            console.print(f"Tokens: {session.token_usage.total_tokens}")
        else:
            console.print(f"[red]Session not found: {session_id}[/red]")
    else:
        # List all sessions
        all_sessions = manager.list_sessions()
        
        if not all_sessions:
            console.print("[yellow]No sessions found[/yellow]")
            return
        
        console.print("[bold]Sessions:[/bold]")
        console.print()
        
        for s in all_sessions[:20]:  # Limit to 20
            console.print(f"  [cyan]{s['id']}[/cyan]")
            console.print(f"    Model: {s['model']}, Messages: {s['message_count']}, Tokens: {s['token_count']}")
            console.print(f"    Updated: {s['updated_at']}")
            console.print()


@main.command()
@click.argument("session_id")
@click.confirmation_option(prompt="Are you sure you want to delete this session?")
@click.pass_context
def delete_session(ctx, session_id):
    """Delete a session"""
    manager = SessionManager()
    
    if manager.delete_session(session_id):
        console.print(f"[green]Session deleted: {session_id}[/green]")
    else:
        console.print(f"[red]Session not found: {session_id}[/red]")


@main.command()
@click.pass_context
def config_show(ctx):
    """Show current configuration"""
    config = ctx.obj["config"]
    
    console.print("[bold]Configuration:[/bold]")
    console.print(f"Project: {ctx.obj['project_path']}")
    console.print()
    
    console.print("[bold]Providers:[/bold]")
    for name, prov in config.providers.items():
        console.print(f"  [cyan]{name}[/cyan]: {prov}")
    if not config.providers:
        console.print("  [dim](none configured)[/dim]")
    console.print()
    
    console.print("[bold]Agents:[/bold]")
    for name, agent in config.agents.items():
        console.print(f"  [cyan]{name}[/cyan]: {agent}")
    if not config.agents:
        console.print("  [dim](none configured)[/dim]")
    console.print()
    
    console.print("[bold]Tools:[/bold]")
    for name, tool in config.tools.items():
        console.print(f"  [cyan]{name}[/cyan]: {tool}")
    if not config.tools:
        console.print("  [dim](none configured)[/dim]")
    console.print()
    
    if config.rules:
        console.print("[bold]Rules:[/bold]")
        for rule in config.rules:
            console.print(f"  - {rule}")
        console.print()
    
    if config.ignore_patterns:
        console.print("[bold]Ignore patterns:[/bold]")
        for pattern in config.ignore_patterns:
            console.print(f"  - {pattern}")
        console.print()
    
    if config.custom_instructions:
        console.print("[bold]Custom instructions:[/bold]")
        console.print(Panel(config.custom_instructions, border_style="dim"))


@main.command()
def tools():
    """List available tools"""
    console.print("[bold]Available tools:[/bold]")
    console.print()
    
    for tool_def in ToolRegistry.list_tools():
        console.print(f"[cyan]{tool_def.name}[/cyan]")
        console.print(f"  {tool_def.description}")
        
        if tool_def.parameters:
            console.print("  Parameters:")
            for param in tool_def.parameters:
                required = "[red]*[/red]" if param.required else " "
                console.print(f"    {required} {param.name} ({param.type}): {param.description}")
        
        console.print()


def main_entry():
    """Entry point for the CLI"""
    main()


if __name__ == "__main__":
    main_entry()
