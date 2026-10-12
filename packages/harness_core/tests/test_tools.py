"""Comprehensive unit tests for the HarnessX Tool Registry and individual tools."""

import pytest
from pathlib import Path

from packages.harness_core.contracts.enums import HarnessMode, ToolPermission
from packages.harness_core.contracts.responses import ToolExecutionResult, ToolResult
from packages.harness_core.execution.runner import MockExecutionRunner, RestrictedSubprocessRunner
from packages.harness_core.execution.workspace import WorkspaceManager
from packages.harness_core.tools.base import ToolContext
from packages.harness_core.tools.file_tools import (
    EditFileTool,
    ListDirectoryTool,
    ListFilesTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)
from packages.harness_core.tools.registry import ToolRegistry
from packages.harness_core.tools.terminal_tools import RunTerminalCommandTool, RunTerminalTool


@pytest.fixture
def tool_context(tmp_path: Path):
    ws = WorkspaceManager(tmp_path)
    runner = MockExecutionRunner(default_stdout="ok", default_exit_code=0)
    return ToolContext(
        session_id="test_sess_tools",
        step_index=1,
        workspace=ws,
        runner=runner,
    )


# ==============================================================================
# 1. ReadFileTool Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_read_file_success(tool_context: ToolContext, tmp_path: Path):
    target = tmp_path / "hello.txt"
    target.write_text("Hello, World!\nLine 2\n", encoding="utf-8")

    tool = ReadFileTool()
    res = await tool.execute({"file_path": "hello.txt"}, tool_context)

    assert isinstance(res, ToolResult)
    assert res.success is True
    assert "Hello, World!" in res.output
    assert res.files_touched == ["hello.txt"]
    assert res.metadata["line_count"] == 2
    assert res.metadata["permission"] == ToolPermission.READ_ONLY.value


@pytest.mark.asyncio
async def test_read_file_missing(tool_context: ToolContext):
    tool = ReadFileTool()
    res = await tool.execute({"file_path": "missing_file.txt"}, tool_context)

    assert res.success is False
    assert "File not found" in res.error


@pytest.mark.asyncio
async def test_read_file_empty_input(tool_context: ToolContext):
    tool = ReadFileTool()
    res = await tool.execute({"file_path": ""}, tool_context)

    assert res.success is False
    assert "Invalid input" in res.error


@pytest.mark.asyncio
async def test_read_file_path_traversal_blocked(tool_context: ToolContext):
    tool = ReadFileTool()
    res = await tool.execute({"file_path": "../../secret.txt"}, tool_context)

    assert res.success is False
    assert "Security Violation" in res.error


@pytest.mark.asyncio
async def test_read_file_size_limit_exceeded(tool_context: ToolContext, tmp_path: Path):
    big_file = tmp_path / "large.bin"
    big_file.write_bytes(b"A" * 500)

    # Tool configured with a 100-byte limit
    tool = ReadFileTool(max_file_size_bytes=100)
    res = await tool.execute({"file_path": "large.bin"}, tool_context)

    assert res.success is False
    assert "File size limit exceeded" in res.error


# ==============================================================================
# 2. WriteFileTool Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_write_file_success(tool_context: ToolContext, tmp_path: Path):
    tool = WriteFileTool()
    res = await tool.execute(
        {"file_path": "subdir/created.py", "content": "x = 42\n"},
        tool_context,
    )

    assert res.success is True
    assert "Successfully wrote" in res.output
    assert res.metadata["bytes_written"] == len(b"x = 42\n")

    created = tmp_path / "subdir" / "created.py"
    assert created.exists()
    assert created.read_text(encoding="utf-8") == "x = 42\n"


@pytest.mark.asyncio
async def test_write_file_empty_input(tool_context: ToolContext):
    tool = WriteFileTool()
    res = await tool.execute({"file_path": "", "content": "data"}, tool_context)
    assert res.success is False
    assert "Invalid input" in res.error

    res2 = await tool.execute({"file_path": "test.txt", "content": None}, tool_context)
    assert res2.success is False
    assert "Invalid input" in res2.error


@pytest.mark.asyncio
async def test_write_file_path_traversal_blocked(tool_context: ToolContext):
    tool = WriteFileTool()
    res = await tool.execute({"file_path": "../outside.txt", "content": "data"}, tool_context)

    assert res.success is False
    assert "Security Violation" in res.error


@pytest.mark.asyncio
async def test_write_file_size_limit_exceeded(tool_context: ToolContext):
    tool = WriteFileTool(max_file_size_bytes=50)
    res = await tool.execute(
        {"file_path": "big.txt", "content": "X" * 100},
        tool_context,
    )

    assert res.success is False
    assert "Write size limit exceeded" in res.error


# ==============================================================================
# 3. EditFileTool Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_edit_file_success(tool_context: ToolContext, tmp_path: Path):
    target = tmp_path / "source.py"
    target.write_text("def run():\n    return False\n", encoding="utf-8")

    tool = EditFileTool()
    res = await tool.execute(
        {
            "file_path": "source.py",
            "target_content": "return False",
            "replacement_content": "return True",
        },
        tool_context,
    )

    assert res.success is True
    assert "Successfully edited" in res.output
    assert target.read_text(encoding="utf-8") == "def run():\n    return True\n"


@pytest.mark.asyncio
async def test_edit_file_input_validations(tool_context: ToolContext):
    tool = EditFileTool()

    # Empty path
    r1 = await tool.execute(
        {"file_path": "", "target_content": "a", "replacement_content": "b"},
        tool_context,
    )
    assert r1.success is False
    assert "Invalid input" in r1.error

    # Empty target
    r2 = await tool.execute(
        {"file_path": "test.py", "target_content": "", "replacement_content": "b"},
        tool_context,
    )
    assert r2.success is False
    assert "Invalid input" in r2.error


@pytest.mark.asyncio
async def test_edit_file_multiple_matches_error(tool_context: ToolContext, tmp_path: Path):
    target = tmp_path / "repeat.txt"
    target.write_text("item\nitem\n", encoding="utf-8")

    tool = EditFileTool()
    res = await tool.execute(
        {"file_path": "repeat.txt", "target_content": "item", "replacement_content": "replaced"},
        tool_context,
    )

    assert res.success is False
    assert "matched 2 times" in res.error


# ==============================================================================
# 4. ListFilesTool & ListDirectoryTool Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_list_directory_tool(tool_context: ToolContext, tmp_path: Path):
    (tmp_path / "file1.py").write_text("# 1", encoding="utf-8")
    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "file2.py").write_text("# 2", encoding="utf-8")

    tool = ListDirectoryTool()
    assert tool.name == "list_files"

    res = await tool.execute({"directory_path": "", "recursive": True}, tool_context)
    assert res.success is True
    assert "file1.py" in res.output
    assert "pkg/file2.py" in res.output
    assert res.metadata["file_count"] == 2


@pytest.mark.asyncio
async def test_list_directory_path_traversal(tool_context: ToolContext):
    tool = ListDirectoryTool()
    res = await tool.execute({"directory_path": "../../"}, tool_context)
    assert res.success is False
    assert "Security Violation" in res.error


# ==============================================================================
# 5. SearchFilesTool Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_search_files_literal_and_regex(tool_context: ToolContext, tmp_path: Path):
    (tmp_path / "code.py").write_text(
        "import math\n\ndef calc(x):\n    return math.sqrt(x)\n",
        encoding="utf-8",
    )

    tool = SearchFilesTool()

    # Literal search
    r_lit = await tool.execute({"query": "math.sqrt"}, tool_context)
    assert r_lit.success is True
    assert len(r_lit.output) == 1
    assert r_lit.output[0]["line"] == 4

    # Regex search
    r_reg = await tool.execute({"query": r"def\s+calc", "is_regex": True}, tool_context)
    assert r_reg.success is True
    assert len(r_reg.output) == 1
    assert r_reg.output[0]["line"] == 3


@pytest.mark.asyncio
async def test_search_files_empty_query(tool_context: ToolContext):
    tool = SearchFilesTool()
    res = await tool.execute({"query": ""}, tool_context)
    assert res.success is False
    assert "Invalid input" in res.error


# ==============================================================================
# 6. RunTerminalTool & Runner Interface Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_run_terminal_tool_success(tool_context: ToolContext):
    tool = RunTerminalTool()
    tool_context.runner.set_command_result("pytest", 0, "All tests passed", "")

    res = await tool.execute({"command": "pytest", "timeout_seconds": 30}, tool_context)
    assert res.success is True
    assert "Exit Code: 0" in res.output
    assert "All tests passed" in res.output


@pytest.mark.asyncio
async def test_run_terminal_tool_failure(tool_context: ToolContext):
    tool = RunTerminalTool()
    tool_context.runner.set_command_result("bad_cmd", 1, "", "Command not found")

    res = await tool.execute({"command": "bad_cmd"}, tool_context)
    assert res.success is False
    assert "Exit Code: 1" in res.output
    assert res.error == "Command not found"


@pytest.mark.asyncio
async def test_run_terminal_tool_empty_command(tool_context: ToolContext):
    tool = RunTerminalTool()
    res = await tool.execute({"command": "   "}, tool_context)
    assert res.success is False
    assert "Empty command" in res.error


# ==============================================================================
# 7. ToolRegistry Mode Filtering & Aliases
# ==============================================================================

def test_tool_registry_registration_and_aliases():
    reg = ToolRegistry.create_default()

    # Direct name
    t1 = reg.get_tool("read_file")
    assert isinstance(t1, ReadFileTool)

    # Alias name: list_directory -> list_files
    t2 = reg.get_tool("list_directory")
    assert isinstance(t2, ListFilesTool)

    # Alias name: run_terminal -> run_terminal_command
    t3 = reg.get_tool("run_terminal")
    assert isinstance(t3, RunTerminalCommandTool)


def test_tool_registry_mode_restrictions():
    reg = ToolRegistry.create_default()

    # GUIDED: File-only
    guided = reg.get_tools_for_mode(HarnessMode.GUIDED)
    names = [t.name for t in guided]
    assert "run_terminal_command" not in names
    assert "write_file" in names

    # DIRECT: Terminal-focused
    direct = reg.get_tools_for_mode(HarnessMode.DIRECT)
    d_names = [t.name for t in direct]
    assert "run_terminal_command" in d_names

    # Schema declarations
    schemas = reg.export_schemas_for_mode(HarnessMode.HYBRID)
    assert len(schemas) == 6
    assert all("name" in s and "parameters" in s for s in schemas)
