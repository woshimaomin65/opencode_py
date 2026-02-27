"""
Test module for OpenCode.

Tests for verifying module correctness.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from opencode import Config, Provider, Session, Agent, Tool
        print("  ✓ Main imports")
    except ImportError as e:
        print(f"  ✗ Main imports failed: {e}")
        return False
    
    try:
        from config import Config, ConfigData
        print("  ✓ Config module")
    except ImportError as e:
        print(f"  ✗ Config module failed: {e}")
        return False
    
    try:
        from provider import (
            BaseProvider,
            ProviderType,
            AnthropicProvider,
            OpenAIProvider,
            GoogleProvider,
            Message,
            Response,
        )
        print("  ✓ Provider module")
    except ImportError as e:
        print(f"  ✗ Provider module failed: {e}")
        return False
    
    try:
        from tool import (
            BaseTool,
            ToolDefinition,
            ToolRegistry,
            ReadTool,
            WriteTool,
            EditTool,
            ShellTool,
            SearchTool,
        )
        print("  ✓ Tool module")
    except ImportError as e:
        print(f"  ✗ Tool module failed: {e}")
        return False
    
    try:
        from session import Session, SessionManager, Message, TokenUsage
        print("  ✓ Session module")
    except ImportError as e:
        print(f"  ✗ Session module failed: {e}")
        return False
    
    try:
        from agent import Agent, AgentConfig
        print("  ✓ Agent module")
    except ImportError as e:
        print(f"  ✗ Agent module failed: {e}")
        return False
    
    try:
        from permission import PermissionManager, PermissionLevel
        print("  ✓ Permission module")
    except ImportError as e:
        print(f"  ✗ Permission module failed: {e}")
        return False
    
    try:
        from mcp import MCPServer, MCPManager, MCPServerConfig
        print("  ✓ MCP module")
    except ImportError as e:
        print(f"  ✗ MCP module failed: {e}")
        return False
    
    try:
        from util import (
            md5_hash,
            normalize_path,
            truncate_text,
            format_bytes,
        )
        print("  ✓ Util module")
    except ImportError as e:
        print(f"  ✗ Util module failed: {e}")
        return False
    
    print("All imports successful!\n")
    return True


def test_config():
    """Test configuration module."""
    print("Testing Config module...")
    
    from config import Config
    
    # Create config with temp directory
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config(project_root=Path(tmpdir)).load()
        
        # Test properties
        assert config.providers == {}
        assert config.agents == {}
        assert config.tools == {}
        assert config.rules == []
        assert config.ignore_patterns == []
        
        print("  ✓ Config creation and properties")
        
        # Test save and load
        config._config_data.providers["test"] = {"model": "test-model"}
        config.save()
        
        # Reload
        config2 = Config(project_root=Path(tmpdir)).load()
        assert "test" in config2.providers
        
        print("  ✓ Config save and load")
    
    print("Config tests passed!\n")
    return True


def test_tool_definitions():
    """Test tool definitions."""
    print("Testing Tool definitions...")
    
    from tool import ReadTool, WriteTool, EditTool, ShellTool, SearchTool
    from tool import ToolRegistry, init_default_tools
    
    # Initialize default tools
    init_default_tools()
    
    # Test tool definitions
    read_tool = ReadTool()
    assert read_tool.definition.name == "read"
    assert "file" in read_tool.definition.description.lower()
    print("  ✓ ReadTool definition")
    
    write_tool = WriteTool()
    assert write_tool.definition.name == "write"
    print("  ✓ WriteTool definition")
    
    edit_tool = EditTool()
    assert edit_tool.definition.name == "edit"
    print("  ✓ EditTool definition")
    
    shell_tool = ShellTool()
    assert shell_tool.definition.name == "shell"
    print("  ✓ ShellTool definition")
    
    search_tool = SearchTool()
    assert search_tool.definition.name == "search"
    print("  ✓ SearchTool definition")
    
    # Test registry
    assert ToolRegistry.get("read") is not None
    assert ToolRegistry.get("write") is not None
    assert ToolRegistry.get("nonexistent") is None
    
    print("  ✓ Tool registry")
    
    # Test tool listing
    tools = ToolRegistry.list_tools()
    assert len(tools) >= 5
    
    print("  ✓ Tool listing")
    
    print("Tool definition tests passed!\n")
    return True


async def test_tool_execution():
    """Test tool execution."""
    print("Testing Tool execution...")
    
    from tool import (
        ReadTool, WriteTool, EditTool, ShellTool, SearchTool,
        ToolRegistry, init_default_tools, ToolStatus,
    )
    import tempfile
    
    init_default_tools()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        test_file = tmpdir / "test.txt"
        
        # Test WriteTool
        write_tool = WriteTool()
        result = await write_tool.execute(path=str(test_file), content="Hello, World!")
        assert result.status == ToolStatus.SUCCESS
        print("  ✓ WriteTool execution")
        
        # Test ReadTool
        read_tool = ReadTool()
        result = await read_tool.execute(path=str(test_file))
        assert result.status == ToolStatus.SUCCESS
        assert result.content == "Hello, World!"
        print("  ✓ ReadTool execution")
        
        # Test EditTool
        edit_tool = EditTool()
        result = await edit_tool.execute(
            path=str(test_file),
            edits=[{"search": "World", "replace": "Python"}]
        )
        assert result.status == ToolStatus.SUCCESS
        
        # Verify edit
        result = await read_tool.execute(path=str(test_file))
        assert result.content == "Hello, Python!"
        print("  ✓ EditTool execution")
        
        # Test ShellTool
        shell_tool = ShellTool()
        result = await shell_tool.execute(command="echo 'test'")
        assert result.status == ToolStatus.SUCCESS
        assert "test" in result.content["stdout"]
        print("  ✓ ShellTool execution")
        
        # Test SearchTool
        result = await SearchTool().execute(pattern="Python", path=str(tmpdir))
        assert result.status == ToolStatus.SUCCESS
        assert len(result.content) > 0
        print("  ✓ SearchTool execution")
        
        # Test error handling
        result = await read_tool.execute(path="/nonexistent/file.txt")
        assert result.status == ToolStatus.ERROR
        print("  ✓ Error handling")
    
    print("Tool execution tests passed!\n")
    return True


def test_session():
    """Test session module."""
    print("Testing Session module...")
    
    from session import Session, SessionManager, TokenUsage
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "sessions"
        
        # Test session creation
        session = Session.create(
            model="test-model",
            provider="test-provider",
            storage_path=storage_path,
        )
        assert session.id is not None
        assert session.model == "test-model"
        assert session.provider == "test-provider"
        print("  ✓ Session creation")
        
        # Test message adding
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")
        assert len(session.messages) == 2
        print("  ✓ Message adding")
        
        # Test token tracking
        session.add_token_usage(100, 50)
        assert session.token_usage.input_tokens == 100
        assert session.token_usage.output_tokens == 50
        assert session.token_usage.total_tokens == 150
        print("  ✓ Token tracking")
        
        # Test session save
        session_path = session.save()
        assert session_path.exists()
        print("  ✓ Session save")
        
        # Test session load
        loaded_session = Session.load(session.id, storage_path)
        assert loaded_session is not None
        assert loaded_session.id == session.id
        assert len(loaded_session.messages) == 2
        print("  ✓ Session load")
        
        # Test session manager
        manager = SessionManager(storage_path)
        sessions = manager.list_sessions()
        assert len(sessions) >= 1
        print("  ✓ Session manager")
        
        # Test session clear
        session.clear()
        assert len(session.messages) == 0
        print("  ✓ Session clear")
    
    print("Session tests passed!\n")
    return True


def test_permission():
    """Test permission module."""
    print("Testing Permission module...")
    
    from permission import PermissionManager, PermissionLevel
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "permissions.json"
        
        # Test permission manager creation
        manager = PermissionManager(storage_path)
        print("  ✓ PermissionManager creation")
        
        # Test default permissions
        assert manager.check_permission("read") == PermissionLevel.ALLOW
        assert manager.check_permission("search") == PermissionLevel.ALLOW
        print("  ✓ Default permissions")
        
        # Test adding rules
        manager.allow("write", pattern="*.txt")
        assert manager.check_permission("write", {"path": "test.txt"}) == PermissionLevel.ALLOW
        print("  ✓ Adding allow rule")
        
        manager.deny("shell", pattern="rm*")
        print("  ✓ Adding deny rule")
        
        # Test session-only rules
        manager.allow("edit", session_only=True)
        assert manager.check_permission("edit") == PermissionLevel.ALLOW
        print("  ✓ Session-only rules")
        
        # Test rule listing
        rules = manager.list_rules()
        assert len(rules) > 0
        print("  ✓ Rule listing")
    
    print("Permission tests passed!\n")
    return True


def test_util():
    """Test utility functions."""
    print("Testing Util module...")
    
    from util import (
        md5_hash,
        sha256_hash,
        truncate_text,
        normalize_path,
        match_glob,
        format_bytes,
        format_duration,
    )
    
    # Test hashing
    assert md5_hash("hello") == "5d41402abc4b2a76b9719d911017c592"
    assert sha256_hash("hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    print("  ✓ Hash functions")
    
    # Test text truncation
    assert truncate_text("hello", 10) == "hello"
    assert truncate_text("hello world", 8) == "hello..."
    print("  ✓ Text truncation")
    
    # Test path normalization
    path = normalize_path("test.txt", Path("/tmp"))
    assert str(path).endswith("test.txt")
    print("  ✓ Path normalization")
    
    # Test glob matching
    assert match_glob("test.py", ["*.py"]) == True
    assert match_glob("test.txt", ["*.py"]) == False
    print("  ✓ Glob matching")
    
    # Test formatting
    assert "KB" in format_bytes(1024)
    assert "ms" in format_duration(0.5)
    assert "s" in format_duration(5)
    print("  ✓ Formatting functions")
    
    print("Util tests passed!\n")
    return True


def test_provider_types():
    """Test provider type definitions."""
    print("Testing Provider types...")
    
    from provider import ProviderType, ProviderRegistry, Message, Response
    
    # Test provider types
    assert ProviderType.ANTHROPIC.value == "anthropic"
    assert ProviderType.OPENAI.value == "openai"
    assert ProviderType.GOOGLE.value == "google"
    print("  ✓ Provider types")
    
    # Test message creation
    msg = Message(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"
    print("  ✓ Message creation")
    
    # Test response creation
    resp = Response(content="Hi", model="test")
    assert resp.content == "Hi"
    assert resp.model == "test"
    print("  ✓ Response creation")
    
    # Test provider registry
    from provider import AnthropicProvider, OpenAIProvider, GoogleProvider
    assert ProviderRegistry.get("anthropic") == AnthropicProvider
    assert ProviderRegistry.get("openai") == OpenAIProvider
    assert ProviderRegistry.get("google") == GoogleProvider
    print("  ✓ Provider registry")
    
    print("Provider type tests passed!\n")
    return True


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("OpenCode Module Tests")
    print("=" * 60)
    print()
    
    tests = [
        ("Imports", test_imports),
        ("Config", test_config),
        ("Tool Definitions", test_tool_definitions),
        ("Session", test_session),
        ("Permission", test_permission),
        ("Util", test_util),
        ("Provider Types", test_provider_types),
        ("Tool Execution", lambda: asyncio.run(test_tool_execution())),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"FAILED: {name}\n")
        except Exception as e:
            failed += 1
            print(f"ERROR in {name}: {e}\n")
            import traceback
            traceback.print_exc()
    
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
