# OpenCode Python - Session and Agent Module Translation

This document describes the translation of OpenCode's Session and Agent core modules from TypeScript to Python.

## Translated Modules

### Session Module (`opencode/session/`)

#### 1. `models.py` (from `session.sql.ts`)
Database models using SQLAlchemy ORM:
- `SessionModel` - Session table
- `MessageModel` - Message table  
- `PartModel` - Part table
- `TodoModel` - Todo table
- `PermissionModel` - Permission table
- Pydantic models for validation and serialization

#### 2. `manager.py` (from `session/index.ts`)
Session management core:
- `SessionManager` - Main session manager class
- `Database` - Database connection manager
- CRUD operations for sessions
- Message and part management
- Token usage calculation
- Session sharing (placeholder)
- Event publishing via Bus

Key functions:
- `create()` - Create new session
- `get()` - Get session by ID
- `fork()` - Fork existing session
- `delete()` - Delete session
- `set_title()`, `set_archived()`, `set_permission()` - Update operations
- `update_message()`, `update_part()` - Message operations
- `calculate_usage()` - Token and cost calculation

#### 3. `message_v2.py` (from `session/message-v2.ts`)
Message V2 format and handling:
- Error types: `OutputLengthError`, `AbortedError`, `APIError`, etc.
- Part types: `TextPart`, `ToolPart`, `FilePart`, `ReasoningPart`, etc.
- Message types: `UserMessage`, `AssistantMessage`
- Tool state types: `ToolStatePending`, `ToolStateRunning`, etc.
- Utility functions:
  - `filter_compacted()` - Filter compacted messages
  - `to_model_messages()` - Convert to provider format
  - `from_error()` - Convert exceptions to message errors

#### 4. `prompt.py` (from `session/prompt.ts`)
Session prompting system:
- `SessionPrompt` - Main prompt handler class
- `PromptInput`, `LoopInput` - Input models
- Conversation loop processing
- User message creation
- Tool resolution
- Structured output handling

### Agent Module (`opencode/agent/`)

#### 1. `agent.py` (enhanced)
Agent core logic with enhancements:
- `AgentMode` enum - SUBAGENT, PRIMARY, ALL
- `AgentInfo` model - Agent configuration
- `AgentRegistry` - Agent registration and lookup
- `Agent` class - Main agent execution
- Built-in agents: build, plan, general, explore, compaction, title, summary

Key features:
- Multiple agent types support
- Tool integration
- Conversation loop with streaming support
- Permission handling
- Token tracking

#### 2. `prompt/` - Agent Prompt Templates
- `compaction.txt` - Conversation summarization prompt
- `explore.txt` - Code exploration agent prompt
- `title.txt` - Title generation prompt
- `summary.txt` - Conversation summary prompt

## Architecture

### Database Layer
- SQLAlchemy ORM for database operations
- SQLite by default (configurable)
- CASCADE delete for referential integrity
- JSON columns for flexible data storage

### Event System
- Bus-based event publishing
- Events: Created, Updated, Deleted, Error
- Effect queue for post-transaction actions

### Message Format
- V2 message format with parts
- Support for multiple part types
- Tool state tracking
- Streaming support

## Key Differences from TypeScript

1. **Database**: SQLAlchemy ORM instead of Drizzle ORM
2. **Validation**: Pydantic instead of Zod
3. **Async**: asyncio instead of native promises
4. **Types**: Python type hints instead of TypeScript types
5. **Imports**: Standard Python imports instead of path aliases

## Usage Examples

### Session Management

```python
from opencode.session import SessionManager, Database

# Initialize database
Database.initialize("sqlite:///./opencode.db")

# Create session manager
manager = SessionManager(
    project_id="my-project",
    directory="/path/to/project",
)

# Create session
session = manager.create(title="My Session")

# Add message
manager.update_message({
    "id": "msg-1",
    "sessionID": session.id,
    "role": "user",
    "time": {"created": 1234567890},
    "agent": "build",
    "model": {"providerID": "anthropic", "modelID": "claude-sonnet"},
})

# List sessions
for s in manager.list(limit=10):
    print(f"{s.id}: {s.title}")
```

### Agent Execution

```python
from opencode.agent import Agent, AgentConfig

# Create agent
config = AgentConfig(
    name="build",
    model="claude-sonnet-4-20250514",
    provider="anthropic",
    tools=["read", "write", "bash"],
)

agent = Agent(config=config)

# Run agent
response = await agent.run("Help me fix this bug...")
print(response)
```

### Message V2

```python
from opencode.session import (
    UserMessage,
    AssistantMessage,
    TextPart,
    MessageWithParts,
    filter_compacted,
)

# Create message with parts
msg = MessageWithParts(
    info=UserMessage(
        id="msg-1",
        sessionID="session-1",
        time={"created": 1234567890},
        agent="build",
        model={"providerID": "anthropic", "modelID": "claude-sonnet"},
    ),
    parts=[
        TextPart(
            id="part-1",
            sessionID="session-1",
            messageID="msg-1",
            text="Hello!",
        )
    ],
)

# Filter and convert
filtered = filter_compacted([msg])
model_msgs = to_model_messages(filtered, model_info)
```

## Testing

Run the test suite:

```bash
cd /Users/maomin/programs/vscode/opencode_py
python -m opencode.tests.test_session_agent
```

## Dependencies

- `sqlalchemy` - Database ORM
- `pydantic` - Data validation
- `anthropic` - Anthropic API (optional)
- `openai` - OpenAI API (optional)
- `google-generativeai` - Google API (optional)

## TODO

- [ ] Complete SessionProcessor implementation
- [ ] Add SessionCompaction module
- [ ] Implement SessionSummary module
- [ ] Add SessionRevert module
- [ ] Complete sharing integration
- [ ] Add comprehensive error handling
- [ ] Performance optimization
- [ ] More extensive test coverage
