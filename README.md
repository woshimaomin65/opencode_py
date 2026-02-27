# OpenCode Python

Python port of the OpenCode AI-powered coding assistant.

## Overview

OpenCode is an AI-powered coding assistant that helps developers write, edit, and understand code. This is a Python port of the original TypeScript/JavaScript implementation.

## Features

- **Multi-provider AI Support**: Anthropic (Claude), OpenAI (GPT), Google (Gemini), and more
- **Tool System**: Built-in tools for reading, writing, editing files, shell commands, and search
- **Session Management**: Persistent conversation history with token tracking
- **MCP Integration**: Model Context Protocol support for external tools
- **Permission System**: Fine-grained control over tool execution
- **CLI Interface**: Command-line interface with interactive mode
- **Plugin System**: Extensible architecture for custom functionality

## Installation

### Prerequisites

- Python 3.11 or higher
- pip or uv package manager

### Install with pip

```bash
pip install -e .
```

### Install with uv

```bash
uv pip install -e .
```

### Install with development dependencies

```bash
pip install -e ".[dev]"
```

## Configuration

OpenCode supports multiple configuration sources:

1. **Global config**: `~/.opencode.json`
2. **Project config**: `.opencode.json` in project root
3. **Directory config**: `.opencode/*.json` in project directories

### Example Configuration

```json
{
  "providers": {
    "anthropic": {
      "model": "claude-sonnet-4-20250514",
      "api_key": "your-api-key"
    },
    "openai": {
      "model": "gpt-4o",
      "api_key": "your-api-key"
    }
  },
  "agents": {
    "default": {
      "model": "claude-sonnet-4-20250514",
      "provider": "anthropic",
      "tools": ["read", "write", "edit", "shell", "search"]
    }
  },
  "rules": [
    "Always use TypeScript for new files",
    "Follow existing code style"
  ],
  "ignore": [
    "node_modules/**",
    ".git/**",
    "**/*.pyc"
  ]
}
```

## Usage

### Run a Single Prompt

```bash
# Basic usage
opencode run "Explain how this code works"

# With specific model
opencode run -m claude-opus-4-20250514 "Refactor this function"

# Using stdin
cat file.py | opencode run "Add type hints"
```

### Interactive Mode

```bash
# Start interactive chat
opencode interactive

# Continue a previous session
opencode interactive -s <session-id>
```

### Session Management

```bash
# List sessions
opencode sessions

# Show specific session
opencode sessions --session-id <id>

# Delete a session
opencode delete-session <id>
```

### Show Configuration

```bash
# Show current configuration
opencode config

# List available tools
opencode tools
```

## API Usage

### Basic Agent Usage

```python
import asyncio
from opencode.agent import Agent
from opencode.tool import init_default_tools

# Initialize tools
init_default_tools()

async def main():
    # Create agent
    agent = Agent.create(
        model="claude-sonnet-4-20250514",
        provider="anthropic",
        tools=["read", "write", "edit", "shell", "search"],
    )
    
    # Run a task
    response = await agent.run("Create a Python function to calculate fibonacci")
    print(response)

asyncio.run(main())
```

### Using Provider Directly

```python
import asyncio
from opencode.provider import get_provider, Message

async def main():
    provider = get_provider(
        provider_type="anthropic",
        model="claude-sonnet-4-20250514",
    )
    
    messages = [
        Message(role="user", content="Hello, how are you?"),
    ]
    
    response = await provider.complete(messages)
    print(response.content)

asyncio.run(main())
```

### Configuration Management

```python
from pathlib import Path
from opencode.config import Config

# Load configuration
config = Config(project_root=Path("/path/to/project")).load()

# Access settings
print(config.providers)
print(config.agents)
print(config.rules)
print(config.custom_instructions)
```

### Session Management

```python
from opencode.session import Session, SessionManager

# Create session manager
manager = SessionManager()

# Create new session
session = manager.create_session(model="claude-sonnet-4-20250514")

# Load existing session
session = manager.get_session("session-id")

# List all sessions
sessions = manager.list_sessions()
```

## Architecture

```
opencode/
├── __init__.py          # Package exports
├── cli/                 # Command-line interface
│   ├── main.py          # CLI entry point
│   └── commands/        # CLI commands
├── config/              # Configuration management
│   └── config.py        # Config loader and merger
├── provider/            # AI provider integration
│   └── provider.py      # Provider abstraction and implementations
├── session/             # Session management
│   └── session.py       # Session storage and retrieval
├── agent/               # Agent execution
│   └── agent.py         # Agent loop and tool integration
├── tool/                # Tool system
│   └── tool.py          # Tool definitions and execution
├── permission/          # Permission management
│   └── permission.py    # Permission rules and enforcement
├── mcp/                 # MCP integration
│   └── mcp.py           # MCP server management
├── plugin/              # Plugin system
├── auth/                # Authentication
├── project/             # Project management
├── store/               # Data storage
└── util/                # Utilities
    └── util.py          # Common utilities
```

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black opencode/
ruff check opencode/
```

### Type Checking

```bash
mypy opencode/
```

## Environment Variables

- `ANTHROPIC_API_KEY`: Anthropic API key
- `OPENAI_API_KEY`: OpenAI API key
- `GOOGLE_API_KEY` or `GEMINI_API_KEY`: Google API key

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
