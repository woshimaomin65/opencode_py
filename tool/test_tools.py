"""
Test module for OpenCode tools.

Tests all core tool implementations:
- ReadTool
- WriteTool
- EditTool
- BashTool
- SearchTool
- WebSearchTool
- WebFetchTool
- LspTool
- ExitTool
"""

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from opencode.tool.tool import ToolContext, ToolStatus, ToolRegistry
from opencode.tool.read import ReadTool, ReadToolConfig
from opencode.tool.write import WriteTool, WriteToolConfig
from opencode.tool.edit import EditTool, EditToolConfig
from opencode.tool.bash import BashTool, BashToolConfig
from opencode.tool.search import SearchTool, SearchToolConfig
from opencode.tool.web import WebSearchTool, WebFetchTool
from opencode.tool.lsp import LspTool
from opencode.tool.exit import ExitTool, PlanEnterTool, PlanExitTool


class MockToolContext(ToolContext):
    """Mock context for testing."""
    
    def __init__(self, working_dir: Optional[Path] = None):
        super().__init__(
            session_id="test-session",
            message_id="test-message",
            agent="test-agent",
            working_dir=working_dir or Path.cwd(),
        )
        self.permission_requests = []
    
    async def ask(self, permission: str, patterns: list[str], always: list[str], metadata: dict) -> None:
        """Mock permission request - just record it."""
        self.permission_requests.append({
            "permission": permission,
            "patterns": patterns,
            "always": always,
            "metadata": metadata,
        })


class TestReadTool(unittest.IsolatedAsyncioTestCase):
    """Test cases for ReadTool."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.ctx = MockToolContext(self.temp_path)
        self.tool = ReadTool(ReadToolConfig(working_dir=self.temp_path))
        
        # Create test files
        self.test_file = self.temp_path / "test.txt"
        self.test_file.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n")
        
        self.test_dir = self.temp_path / "test_dir"
        self.test_dir.mkdir()
        (self.test_dir / "file1.txt").write_text("content1")
        (self.test_dir / "file2.txt").write_text("content2")
    
    async def asyncTearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    async def test_read_file(self):
        """Test reading a file."""
        result = await self.tool.execute(self.ctx, filePath=str(self.test_file))
        
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertIn("Line 1", result.content)
        self.assertIn("Line 5", result.content)
    
    async def test_read_file_with_limit(self):
        """Test reading a file with line limit."""
        result = await self.tool.execute(self.ctx, filePath=str(self.test_file), limit=2)
        
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertIn("Line 1", result.content)
        self.assertIn("Line 2", result.content)
        self.assertNotIn("Line 3", result.content)
    
    async def test_read_file_with_offset(self):
        """Test reading a file with offset."""
        result = await self.tool.execute(self.ctx, filePath=str(self.test_file), offset=3, limit=2)
        
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertIn("3: Line 3", result.content)
        self.assertIn("4: Line 4", result.content)
        self.assertNotIn("Line 1", result.content)
    
    async def test_read_directory(self):
        """Test reading a directory."""
        result = await self.tool.execute(self.ctx, filePath=str(self.test_dir))
        
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertIn("file1.txt", result.content)
        self.assertIn("file2.txt", result.content)
    
    async def test_read_nonexistent_file(self):
        """Test reading a nonexistent file."""
        result = await self.tool.execute(self.ctx, filePath=str(self.temp_path / "nonexistent.txt"))
        
        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIn("not found", result.error.lower())
    
    async def test_read_missing_parameter(self):
        """Test reading with missing parameter."""
        result = await self.tool.execute(self.ctx)
        
        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIn("filePath", result.error)


class TestWriteTool(unittest.IsolatedAsyncioTestCase):
    """Test cases for WriteTool."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.ctx = MockToolContext(self.temp_path)
        self.tool = WriteTool(WriteToolConfig(working_dir=self.temp_path))
    
    async def asyncTearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    async def test_write_new_file(self):
        """Test writing a new file."""
        test_file = self.temp_path / "new_file.txt"
        content = "Hello, World!"
        
        result = await self.tool.execute(self.ctx, filePath=str(test_file), content=content)
        
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertTrue(test_file.exists())
        self.assertEqual(test_file.read_text(), content)
    
    async def test_write_overwrite_file(self):
        """Test overwriting an existing file."""
        test_file = self.temp_path / "existing.txt"
        test_file.write_text("old content")
        
        result = await self.tool.execute(self.ctx, filePath=str(test_file), content="new content")
        
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertEqual(test_file.read_text(), "new content")
    
    async def test_write_creates_directories(self):
        """Test that write creates parent directories."""
        test_file = self.temp_path / "subdir" / "nested" / "file.txt"
        
        result = await self.tool.execute(self.ctx, filePath=str(test_file), content="content")
        
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertTrue(test_file.exists())
    
    async def test_write_missing_path(self):
        """Test writing with missing path."""
        result = await self.tool.execute(self.ctx, content="content")
        
        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIn("filePath", result.error)
    
    async def test_write_missing_content(self):
        """Test writing with missing content."""
        test_file = self.temp_path / "test.txt"
        
        result = await self.tool.execute(self.ctx, filePath=str(test_file))
        
        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIn("content", result.error)


class TestEditTool(unittest.IsolatedAsyncioTestCase):
    """Test cases for EditTool."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.ctx = MockToolContext(self.temp_path)
        self.tool = EditTool(EditToolConfig(working_dir=self.temp_path))
        
        # Create test file
        self.test_file = self.temp_path / "edit_test.txt"
        self.test_file.write_text("Hello World\nSecond line\nThird line\n")
    
    async def asyncTearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    async def test_edit_simple_replace(self):
        """Test simple string replacement."""
        result = await self.tool.execute(
            self.ctx,
            filePath=str(self.test_file),
            oldString="World",
            newString="Python",
        )
        
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertEqual(self.test_file.read_text(), "Hello Python\nSecond line\nThird line\n")
    
    async def test_edit_multiline(self):
        """Test multiline replacement."""
        result = await self.tool.execute(
            self.ctx,
            filePath=str(self.test_file),
            oldString="Second line\nThird line",
            newString="New second line",
        )
        
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertEqual(self.test_file.read_text(), "Hello World\nNew second line\n")
    
    async def test_edit_identical_strings(self):
        """Test edit with identical old and new strings."""
        result = await self.tool.execute(
            self.ctx,
            filePath=str(self.test_file),
            oldString="test",
            newString="test",
        )
        
        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIn("identical", result.error.lower())
    
    async def test_edit_nonexistent_file(self):
        """Test editing a nonexistent file."""
        result = await self.tool.execute(
            self.ctx,
            filePath=str(self.temp_path / "nonexistent.txt"),
            oldString="test",
            newString="new",
        )
        
        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIn("not found", result.error.lower())


class TestBashTool(unittest.IsolatedAsyncioTestCase):
    """Test cases for BashTool."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.ctx = MockToolContext(self.temp_path)
        self.tool = BashTool(BashToolConfig(working_dir=self.temp_path))
    
    async def asyncTearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    async def test_bash_simple_command(self):
        """Test simple bash command."""
        result = await self.tool.execute(
            self.ctx,
            command="echo 'Hello World'",
            description="Echo hello world",
        )
        
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertIn("Hello World", result.content.get("stdout", ""))
    
    async def test_bash_exit_code(self):
        """Test command with nonzero exit code."""
        result = await self.tool.execute(
            self.ctx,
            command="exit 1",
            description="Exit with error",
        )
        
        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertEqual(result.content.get("exit_code"), 1)
    
    async def test_bash_working_dir(self):
        """Test command with custom working directory."""
        subdir = self.temp_path / "subdir"
        subdir.mkdir()
        
        result = await self.tool.execute(
            self.ctx,
            command="pwd",
            workdir=str(subdir),
            description="Print working directory",
        )
        
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertIn("subdir", result.content.get("stdout", ""))
    
    async def test_bash_missing_command(self):
        """Test bash with missing command."""
        result = await self.tool.execute(self.ctx, description="Test")
        
        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIn("command", result.error)
    
    async def test_bash_invalid_timeout(self):
        """Test bash with invalid timeout."""
        result = await self.tool.execute(
            self.ctx,
            command="echo test",
            timeout=-100,
            description="Test",
        )
        
        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIn("timeout", result.error.lower())


class TestSearchTool(unittest.IsolatedAsyncioTestCase):
    """Test cases for SearchTool."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.ctx = MockToolContext(self.temp_path)
        self.tool = SearchTool(SearchToolConfig(working_dir=self.temp_path))
        
        # Create test files
        self.file1 = self.temp_path / "test1.py"
        self.file1.write_text("def hello():\n    print('hello')\n")
        
        self.file2 = self.temp_path / "test2.py"
        self.file2.write_text("def world():\n    print('world')\n")
        
        self.file3 = self.temp_path / "test.txt"
        self.file3.write_text("This is a text file\n")
    
    async def asyncTearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    async def test_search_pattern(self):
        """Test searching for a pattern."""
        result = await self.tool.execute(self.ctx, pattern="def ")
        
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertIn("test1.py", result.content)
        self.assertIn("test2.py", result.content)
    
    async def test_search_with_include(self):
        """Test searching with file include filter."""
        result = await self.tool.execute(self.ctx, pattern="def ", include="*.py")
        
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertIn("test1.py", result.content)
        self.assertIn("test2.py", result.content)
        self.assertNotIn("test.txt", result.content)
    
    async def test_search_no_matches(self):
        """Test searching with no matches."""
        result = await self.tool.execute(self.ctx, pattern="xyz123notfound")
        
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertIn("No files found", result.content)
    
    async def test_search_missing_pattern(self):
        """Test search with missing pattern."""
        result = await self.tool.execute(self.ctx)
        
        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIn("pattern", result.error)


class TestWebTools(unittest.IsolatedAsyncioTestCase):
    """Test cases for Web tools."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.ctx = MockToolContext()
        self.search_tool = WebSearchTool()
        self.fetch_tool = WebFetchTool()
    
    async def test_webfetch_invalid_url(self):
        """Test webfetch with invalid URL."""
        result = await self.fetch_tool.execute(self.ctx, url="ftp://invalid.com")
        
        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIn("http", result.error)
    
    async def test_webfetch_missing_url(self):
        """Test webfetch with missing URL."""
        result = await self.fetch_tool.execute(self.ctx)
        
        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIn("url", result.error)
    
    async def test_websearch_missing_query(self):
        """Test websearch with missing query."""
        result = await self.search_tool.execute(self.ctx)
        
        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIn("query", result.error)


class TestLspTool(unittest.IsolatedAsyncioTestCase):
    """Test cases for LspTool."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.ctx = MockToolContext(self.temp_path)
        from opencode.tool.lsp import LspToolConfig
        self.tool = LspTool(LspToolConfig(working_dir=self.temp_path))
        
        # Create test file
        self.test_file = self.temp_path / "test.py"
        self.test_file.write_text("def hello():\n    pass\n")
    
    async def asyncTearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    async def test_lsp_invalid_operation(self):
        """Test LSP with invalid operation."""
        result = await self.tool.execute(
            self.ctx,
            operation="invalidOp",
            filePath=str(self.test_file),
            line=1,
            character=1,
        )
        
        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIn("Invalid operation", result.error)
    
    async def test_lsp_missing_file(self):
        """Test LSP with missing file."""
        result = await self.tool.execute(
            self.ctx,
            operation="goToDefinition",
            filePath=str(self.temp_path / "nonexistent.py"),
            line=1,
            character=1,
        )
        
        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIn("not found", result.error.lower())
    
    async def test_lsp_missing_parameters(self):
        """Test LSP with missing parameters."""
        result = await self.tool.execute(self.ctx, operation="hover")
        
        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIn("filePath", result.error)


class TestExitTool(unittest.IsolatedAsyncioTestCase):
    """Test cases for ExitTool."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.ctx = MockToolContext()
        self.tool = ExitTool()
    
    async def test_exit_success(self):
        """Test successful exit."""
        result = await self.tool.execute(
            self.ctx,
            status="success",
            message="Task completed",
        )
        
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertIn("Task completed", result.content)
        self.assertIn("success", result.content)
    
    async def test_exit_with_summary(self):
        """Test exit with summary."""
        result = await self.tool.execute(
            self.ctx,
            status="success",
            summary="Implemented feature X and fixed bug Y",
        )
        
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertIn("Summary", result.content)
        self.assertIn("Implemented feature X", result.content)


class TestPlanTools(unittest.IsolatedAsyncioTestCase):
    """Test cases for Plan tools."""
    
    async def asyncSetUp(self):
        """Set up test fixtures."""
        self.ctx = MockToolContext()
        self.enter_tool = PlanEnterTool()
        self.exit_tool = PlanExitTool()
    
    async def test_plan_enter(self):
        """Test entering plan mode."""
        result = await self.enter_tool.execute(
            self.ctx,
            goal="Implement authentication",
            constraints="Use OAuth2",
        )
        
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertIn("plan mode", result.content.lower())
        self.assertIn("authentication", result.content)
    
    async def test_plan_enter_missing_goal(self):
        """Test plan enter with missing goal."""
        result = await self.enter_tool.execute(self.ctx)
        
        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIn("goal", result.error)
    
    async def test_plan_exit(self):
        """Test exiting plan mode."""
        result = await self.exit_tool.execute(
            self.ctx,
            plan="1. Setup database\n2. Implement API\n3. Add tests",
            ready=True,
        )
        
        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertIn("plan mode", result.content.lower())
        self.assertIn("Setup database", result.content)
    
    async def test_plan_exit_missing_plan(self):
        """Test plan exit with missing plan."""
        result = await self.exit_tool.execute(self.ctx, ready=True)
        
        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIn("plan", result.error)


class TestToolRegistry(unittest.IsolatedAsyncioTestCase):
    """Test cases for ToolRegistry."""
    
    async def test_register_tool(self):
        """Test registering a tool."""
        tool = ReadTool()
        ToolRegistry.register(tool)
        
        retrieved = ToolRegistry.get("read")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.definition.name, "read")
    
    async def test_get_unknown_tool(self):
        """Test getting an unknown tool."""
        tool = ToolRegistry.get("nonexistent")
        self.assertIsNone(tool)
    
    async def test_list_tools(self):
        """Test listing registered tools."""
        ToolRegistry.register(ReadTool())
        ToolRegistry.register(WriteTool())
        
        tools = ToolRegistry.list_tools()
        names = [t.name for t in tools]
        
        self.assertIn("read", names)
        self.assertIn("write", names)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestReadTool))
    suite.addTests(loader.loadTestsFromTestCase(TestWriteTool))
    suite.addTests(loader.loadTestsFromTestCase(TestEditTool))
    suite.addTests(loader.loadTestsFromTestCase(TestBashTool))
    suite.addTests(loader.loadTestsFromTestCase(TestSearchTool))
    suite.addTests(loader.loadTestsFromTestCase(TestWebTools))
    suite.addTests(loader.loadTestsFromTestCase(TestLspTool))
    suite.addTests(loader.loadTestsFromTestCase(TestExitTool))
    suite.addTests(loader.loadTestsFromTestCase(TestPlanTools))
    suite.addTests(loader.loadTestsFromTestCase(TestToolRegistry))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
