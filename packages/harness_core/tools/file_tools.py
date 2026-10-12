"""File manipulation and inspection tools with strict validation and workspace boundaries."""

import re
import time
from typing import Any, Dict, List, Optional

from packages.harness_core.contracts.enums import ToolPermission
from packages.harness_core.contracts.responses import ToolExecutionResult
from packages.harness_core.exceptions.errors import PathTraversalError
from packages.harness_core.tools.base import BaseTool, ToolContext

# Default maximum allowable file size (5 MB)
DEFAULT_MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024


class ReadFileTool(BaseTool):
    """Reads content from a file inside the workspace."""

    def __init__(self, max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES) -> None:
        self.max_file_size_bytes = max_file_size_bytes

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the complete text contents of a specified file in the workspace."

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.READ_ONLY

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Workspace-relative path to the file to read.",
                }
            },
            "required": ["file_path"],
        }

    async def execute(
        self, arguments: Dict[str, Any], context: ToolContext
    ) -> ToolExecutionResult:
        start_t = time.perf_counter()
        raw_path = arguments.get("file_path")

        # 1. Input validation
        if not raw_path or not str(raw_path).strip():
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error="Invalid input: 'file_path' parameter is required and cannot be empty.",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

        file_path = str(raw_path).strip()

        try:
            # 2. Workspace boundary resolution & path traversal prevention
            abs_p = context.workspace.resolve_path(file_path)

            if not abs_p.is_file():
                return ToolExecutionResult(
                    tool_name=self.name,
                    success=False,
                    error=f"File not found: '{file_path}'",
                    duration_ms=(time.perf_counter() - start_t) * 1000,
                )

            # 3. File size limit enforcement
            file_size = abs_p.stat().st_size
            if file_size > self.max_file_size_bytes:
                return ToolExecutionResult(
                    tool_name=self.name,
                    success=False,
                    error=(
                        f"File size limit exceeded: '{file_path}' is {file_size} bytes "
                        f"(maximum allowed: {self.max_file_size_bytes} bytes)."
                    ),
                    metadata={"file_size_bytes": file_size, "limit_bytes": self.max_file_size_bytes},
                    duration_ms=(time.perf_counter() - start_t) * 1000,
                )

            content = abs_p.read_text(encoding="utf-8", errors="replace")
            # Record read hash for AgentGuard read-before-write validation
            context.workspace.record_read(file_path)

            return ToolExecutionResult(
                tool_name=self.name,
                success=True,
                output=content,
                files_touched=[file_path],
                metadata={
                    "file_size_bytes": file_size,
                    "line_count": len(content.splitlines()),
                    "permission": self.permission.value,
                },
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except PathTraversalError as e:
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error=f"Security Violation: Path traversal blocked: {str(e)}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error=f"Error reading file '{file_path}': {str(e)}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )


class WriteFileTool(BaseTool):
    """Creates or overwrites a file in the workspace."""

    def __init__(self, max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES) -> None:
        self.max_file_size_bytes = max_file_size_bytes

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write text content to a file in the workspace. Creates parent directories if missing."

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.WRITE_FILE

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Workspace-relative path of the file to create or overwrite.",
                },
                "content": {
                    "type": "string",
                    "description": "Full text content to write.",
                },
            },
            "required": ["file_path", "content"],
        }

    async def execute(
        self, arguments: Dict[str, Any], context: ToolContext
    ) -> ToolExecutionResult:
        start_t = time.perf_counter()
        raw_path = arguments.get("file_path")
        content = arguments.get("content")

        # 1. Input validation
        if not raw_path or not str(raw_path).strip():
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error="Invalid input: 'file_path' parameter is required and cannot be empty.",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        if content is None:
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error="Invalid input: 'content' parameter is required.",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

        file_path = str(raw_path).strip()
        encoded_content = content.encode("utf-8")

        # 2. Size limit enforcement
        if len(encoded_content) > self.max_file_size_bytes:
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error=(
                    f"Write size limit exceeded: payload is {len(encoded_content)} bytes "
                    f"(maximum allowed: {self.max_file_size_bytes} bytes)."
                ),
                metadata={"content_size_bytes": len(encoded_content), "limit_bytes": self.max_file_size_bytes},
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

        try:
            abs_p = context.workspace.resolve_path(file_path)
            abs_p.parent.mkdir(parents=True, exist_ok=True)
            abs_p.write_text(content, encoding="utf-8")
            # Update hash
            context.workspace.record_read(file_path)

            return ToolExecutionResult(
                tool_name=self.name,
                success=True,
                output=f"Successfully wrote {len(content)} characters to '{file_path}'",
                files_touched=[file_path],
                metadata={
                    "bytes_written": len(encoded_content),
                    "line_count": len(content.splitlines()),
                    "permission": self.permission.value,
                },
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except PathTraversalError as e:
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error=f"Security Violation: Path traversal blocked: {str(e)}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error=f"Failed to write file '{file_path}': {str(e)}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )


class EditFileTool(BaseTool):
    """Replaces a targeted substring inside an existing file."""

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return "Edit a file by replacing an exact substring (target_content) with replacement_content."

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.WRITE_FILE

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Workspace-relative path to the file to edit.",
                },
                "target_content": {
                    "type": "string",
                    "description": "Exact text substring to be replaced.",
                },
                "replacement_content": {
                    "type": "string",
                    "description": "New text to substitute in place of target_content.",
                },
            },
            "required": ["file_path", "target_content", "replacement_content"],
        }

    async def execute(
        self, arguments: Dict[str, Any], context: ToolContext
    ) -> ToolExecutionResult:
        start_t = time.perf_counter()
        raw_path = arguments.get("file_path")
        target = arguments.get("target_content")
        replacement = arguments.get("replacement_content")

        # 1. Input validation
        if not raw_path or not str(raw_path).strip():
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error="Invalid input: 'file_path' parameter is required and cannot be empty.",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        if target is None or target == "":
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error="Invalid input: 'target_content' parameter is required and cannot be empty.",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        if replacement is None:
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error="Invalid input: 'replacement_content' parameter is required.",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

        file_path = str(raw_path).strip()

        try:
            abs_p = context.workspace.resolve_path(file_path)
            if not abs_p.is_file():
                return ToolExecutionResult(
                    tool_name=self.name,
                    success=False,
                    error=f"File not found for edit: '{file_path}'",
                    duration_ms=(time.perf_counter() - start_t) * 1000,
                )

            current = abs_p.read_text(encoding="utf-8", errors="replace")
            occurrences = current.count(target)
            if occurrences == 0:
                return ToolExecutionResult(
                    tool_name=self.name,
                    success=False,
                    error=f"Target content not found in '{file_path}'. Make sure it matches exactly.",
                    duration_ms=(time.perf_counter() - start_t) * 1000,
                )
            if occurrences > 1:
                return ToolExecutionResult(
                    tool_name=self.name,
                    success=False,
                    error=f"Target content matched {occurrences} times in '{file_path}'. Provide a more specific snippet.",
                    duration_ms=(time.perf_counter() - start_t) * 1000,
                )

            updated = current.replace(target, replacement, 1)
            abs_p.write_text(updated, encoding="utf-8")
            # Update hash
            context.workspace.record_read(file_path)

            return ToolExecutionResult(
                tool_name=self.name,
                success=True,
                output=f"Successfully edited '{file_path}' (replaced 1 occurrence).",
                files_touched=[file_path],
                metadata={
                    "occurrences_replaced": 1,
                    "permission": self.permission.value,
                },
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except PathTraversalError as e:
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error=f"Security Violation: Path traversal blocked: {str(e)}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error=f"Failed to edit file '{file_path}': {str(e)}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )


class ListFilesTool(BaseTool):
    """Lists files in the workspace."""

    @property
    def name(self) -> str:
        return "list_files"

    @property
    def description(self) -> str:
        return "List files and directories in the workspace."

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.READ_ONLY

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "directory_path": {
                    "type": "string",
                    "description": "Relative subdirectory path (default: root '').",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to list recursively (default: true).",
                },
            },
        }

    async def execute(
        self, arguments: Dict[str, Any], context: ToolContext
    ) -> ToolExecutionResult:
        start_t = time.perf_counter()
        dir_p = arguments.get("directory_path", "")
        recursive = arguments.get("recursive", True)

        try:
            files = context.workspace.list_files(sub_dir=dir_p, recursive=recursive)
            return ToolExecutionResult(
                tool_name=self.name,
                success=True,
                output=files,
                metadata={"file_count": len(files), "directory": dir_p},
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except PathTraversalError as e:
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error=f"Security Violation: Path traversal blocked: {str(e)}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error=f"Error listing files: {str(e)}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )


class SearchFilesTool(BaseTool):
    """Searches workspace files for patterns."""

    @property
    def name(self) -> str:
        return "search_files"

    @property
    def description(self) -> str:
        return "Search file contents across workspace for a string or regex pattern."

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.READ_ONLY

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text substring or regex pattern to search.",
                },
                "is_regex": {
                    "type": "boolean",
                    "description": "Whether query is a regex pattern (default: false).",
                },
                "sub_dir": {
                    "type": "string",
                    "description": "Subdirectory to restrict search within.",
                },
            },
            "required": ["query"],
        }

    async def execute(
        self, arguments: Dict[str, Any], context: ToolContext
    ) -> ToolExecutionResult:
        start_t = time.perf_counter()
        query = arguments.get("query")
        is_regex = arguments.get("is_regex", False)
        sub_dir = arguments.get("sub_dir", "")

        # 1. Input validation
        if not query or not str(query).strip():
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error="Invalid input: 'query' parameter is required and cannot be empty.",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

        matches: List[Dict[str, Any]] = []
        try:
            all_files = context.workspace.list_files(sub_dir=sub_dir)
            pattern = re.compile(query) if is_regex else None

            for rel_f in all_files:
                abs_f = context.workspace.resolve_path(rel_f)
                try:
                    lines = abs_f.read_text(encoding="utf-8", errors="ignore").splitlines()
                    for idx, line in enumerate(lines, 1):
                        matched = bool(pattern.search(line)) if pattern else (query in line)
                        if matched:
                            matches.append({
                                "file": rel_f,
                                "line": idx,
                                "content": line.strip()[:200],
                            })
                            if len(matches) >= 50:
                                break
                except Exception:
                    continue

                if len(matches) >= 50:
                    break

            return ToolExecutionResult(
                tool_name=self.name,
                success=True,
                output=matches,
                metadata={"match_count": len(matches), "query": query},
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except PathTraversalError as e:
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error=f"Security Violation: Path traversal blocked: {str(e)}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error=f"Search failed: {str(e)}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )


# Aliases
ListDirectoryTool = ListFilesTool
