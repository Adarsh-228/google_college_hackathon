"""Tests for sandboxed workspace isolation and path security."""

import pytest
from pathlib import Path
from packages.harness_core.exceptions.errors import PathTraversalError
from packages.harness_core.execution.workspace import WorkspaceManager


def test_workspace_isolation(tmp_path: Path):
    ws = WorkspaceManager(tmp_path)
    safe = ws.resolve_path("sub/file.py")
    assert safe == tmp_path / "sub" / "file.py"

    # Block path traversal
    with pytest.raises(PathTraversalError):
        ws.resolve_path("../../etc/passwd")

    with pytest.raises(PathTraversalError):
        ws.resolve_path("../outside.txt")


def test_workspace_file_hashing_and_reading(tmp_path: Path):
    ws = WorkspaceManager(tmp_path)
    target = tmp_path / "test.txt"
    target.write_text("initial content", encoding="utf-8")

    h1 = ws.compute_hash("test.txt")
    assert h1 is not None
    assert len(h1) == 64  # SHA-256 length

    # Record read
    recorded = ws.record_read("test.txt")
    assert recorded == h1
    assert ws.get_last_read_hash("test.txt") == h1

    # Modify file
    target.write_text("modified content", encoding="utf-8")
    h2 = ws.compute_hash("test.txt")
    assert h2 != h1
    assert ws.get_last_read_hash("test.txt") == h1  # still reflects last read!


def test_workspace_list_files(tmp_path: Path):
    ws = WorkspaceManager(tmp_path)
    (tmp_path / "a.py").write_text("a", encoding="utf-8")
    sub = tmp_path / "dir"
    sub.mkdir()
    (sub / "b.py").write_text("b", encoding="utf-8")

    files = ws.list_files(recursive=True)
    assert "a.py" in files
    assert "dir/b.py" in files
