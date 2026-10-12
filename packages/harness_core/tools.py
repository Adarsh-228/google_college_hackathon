import os
import glob
import re
import subprocess
from typing import Dict, Any, List, Optional, Tuple
from .guard import AgentGuard

class ToolRegistry:
    """
    Manages executable tools and dispatches calls through AgentGuard.
    Supports predefined structured mode and bash-only mode with diff linter.
    """

    def __init__(self, workspace_root: str, guard: AgentGuard):
        self.workspace_root = os.path.realpath(workspace_root)
        self.guard = guard

    def execute_tool(self, name: str, args: Dict[str, Any]) -> Tuple[str, bool, Optional[str]]:
        """
        Executes a tool call.
        Returns (result_observation, is_error, guard_badge).
        """
        guard_badge: Optional[str] = None

        try:
            if name == "read_file":
                output, is_err = self._read_file(
                    path=args.get("path", ""),
                    offset=int(args.get("offset", 1)),
                    limit=int(args.get("limit", 2000)),
                )
                return output, is_err, None

            elif name == "write_file":
                output, is_err, badge = self._write_file(
                    path=args.get("path", ""),
                    content=args.get("content", ""),
                    overwrite=bool(args.get("overwrite", False)),
                )
                return output, is_err, badge

            elif name == "edit_file":
                output, is_err, badge = self._edit_file(
                    path=args.get("path", ""),
                    old_text=args.get("old_text", ""),
                    new_text=args.get("new_text", ""),
                    replace_all=bool(args.get("replace_all", False)),
                )
                return output, is_err, badge

            elif name == "list_files":
                output, is_err = self._list_files(
                    path=args.get("path", "."),
                    recursive=bool(args.get("recursive", False)),
                )
                return output, is_err, None

            elif name == "glob_files":
                output, is_err = self._glob_files(
                    pattern=args.get("pattern", "*"),
                    path=args.get("path", "."),
                )
                return output, is_err, None

            elif name == "grep_text":
                output, is_err = self._grep_text(
                    query=args.get("query", ""),
                    path=args.get("path", "."),
                    include=args.get("include"),
                )
                return output, is_err, None

            elif name == "bash":
                output, is_err, badge = self._bash(
                    command=args.get("command", ""),
                    timeout_seconds=int(args.get("timeout_seconds", 120)),
                    cwd=args.get("cwd", "."),
                )
                return output, is_err, badge

            else:
                return f"[Error: Unknown tool '{name}']", True, None

        except PermissionError as pe:
            return f"[AgentGuard Security Block: {str(pe)}]", True, "RBW_BLOCKED"
        except Exception as e:
            return f"[Error executing '{name}': {str(e)}]", True, None

    # -------------------------------------------------------------
    # Tool Implementations
    # -------------------------------------------------------------
    def _read_file(self, path: str, offset: int = 1, limit: int = 2000) -> Tuple[str, bool]:
        abs_path = self.guard.canonicalize_path(path)
        if not os.path.exists(abs_path):
            return f"[Error: File '{path}' does not exist]", True
        if os.path.isdir(abs_path):
            return f"[Error: '{path}' is a directory. Use list_files instead.]", True

        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            start_idx = max(0, offset - 1)
            end_idx = min(total_lines, start_idx + limit)
            selected_lines = lines[start_idx:end_idx]

            is_full_read = (offset == 1) and (limit >= total_lines)
            full_content = "".join(lines)
            self.guard.record_read(abs_path, is_full_read, full_content)

            formatted = []
            for i, line in enumerate(selected_lines, start=start_idx + 1):
                formatted.append(f"{i:4d} | {line.rstrip('\\r\\n')}")

            header = f"[read_file: {path} (lines {start_idx+1}-{end_idx} of {total_lines}, full_read={is_full_read})]\n"
            return header + "\n".join(formatted), False
        except Exception as e:
            return f"[Error reading '{path}': {str(e)}]", True

    def _write_file(self, path: str, content: str, overwrite: bool = False) -> Tuple[str, bool, Optional[str]]:
        abs_path = self.guard.canonicalize_path(path)
        file_exists = os.path.exists(abs_path)

        if file_exists and not overwrite:
            return (
                f"[Error: File '{path}' already exists. Pass overwrite=True or use edit_file for surgical edits.]",
                True,
                None,
            )

        # RBW check
        allowed, err_msg = self.guard.validate_write_permission(abs_path, is_overwrite=overwrite)
        if not allowed:
            return err_msg or "Write permission denied by RBW gate", True, "RBW_BLOCKED"

        try:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            self.guard.record_mutation(abs_path, content)
            out = f"[write_file: Successfully wrote {len(content)} characters to '{path}']"

            # Post-edit diagnostics
            diag = self.guard.run_post_edit_diagnostics(abs_path)
            badge = None
            if diag:
                out += f"\n\n{diag}"
                badge = "LINT_DETECTED"

            return out, False, badge
        except Exception as e:
            return f"[Error writing '{path}': {str(e)}]", True, None

    def _edit_file(self, path: str, old_text: str, new_text: str, replace_all: bool = False) -> Tuple[str, bool, Optional[str]]:
        abs_path = self.guard.canonicalize_path(path)
        if not os.path.exists(abs_path):
            return f"[Error: File '{path}' does not exist to edit]", True, None

        if old_text == new_text:
            return "[Error: old_text and new_text are identical. No-op rejected.]", True, None

        # RBW check
        allowed, err_msg = self.guard.validate_write_permission(abs_path, is_overwrite=True)
        if not allowed:
            return err_msg or "Edit permission denied by RBW gate", True, "RBW_BLOCKED"

        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            count = content.count(old_text)
            if count == 0:
                return (
                    f"[Error: old_text not found in '{path}'. Please inspect file with read_file first.]",
                    True,
                    None,
                )
            if count > 1 and not replace_all:
                return (
                    f"[Error: old_text appeared {count} times in '{path}'. "
                    f"Provide more surrounding context to disambiguate or pass replace_all=True.]",
                    True,
                    None,
                )

            new_content = content.replace(old_text, new_text) if replace_all else content.replace(old_text, new_text, 1)

            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            self.guard.record_mutation(abs_path, new_content)
            out = f"[edit_file: Successfully replaced {count if replace_all else 1} occurrence(s) in '{path}']"

            # Post-edit diagnostics
            diag = self.guard.run_post_edit_diagnostics(abs_path)
            badge = None
            if diag:
                out += f"\n\n{diag}"
                badge = "LINT_DETECTED"

            return out, False, badge
        except Exception as e:
            return f"[Error editing '{path}': {str(e)}]", True, None

    def _list_files(self, path: str = ".", recursive: bool = False) -> Tuple[str, bool]:
        abs_path = self.guard.canonicalize_path(path)
        if not os.path.isdir(abs_path):
            return f"[Error: '{path}' is not a directory]", True

        ignore = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache"}
        entries = []
        if recursive:
            for root, dirs, files in os.walk(abs_path):
                dirs[:] = [d for d in dirs if d not in ignore]
                rel_root = os.path.relpath(root, self.workspace_root)
                for f in files:
                    entries.append(os.path.join(rel_root, f).replace("\\", "/"))
        else:
            for item in os.listdir(abs_path):
                if item not in ignore:
                    p = os.path.join(path, item).replace("\\", "/")
                    entries.append(f"{p}/" if os.path.isdir(os.path.join(abs_path, item)) else p)

        return "\n".join(sorted(entries)[:200]), False

    def _glob_files(self, pattern: str, path: str = ".") -> Tuple[str, bool]:
        abs_path = self.guard.canonicalize_path(path)
        full_pattern = os.path.join(abs_path, pattern)
        matches = glob.glob(full_pattern, recursive=True)
        rel_matches = [
            os.path.relpath(m, self.workspace_root).replace("\\", "/")
            for m in matches
            if os.path.isfile(m) and ".git" not in m
        ]
        return "\n".join(sorted(rel_matches)[:200]), False

    def _grep_text(self, query: str, path: str = ".", include: Optional[str] = None) -> Tuple[str, bool]:
        abs_path = self.guard.canonicalize_path(path)
        results = []
        try:
            regex = re.compile(query, re.IGNORECASE)
        except re.error as e:
            return f"[Error: Invalid regex '{query}': {str(e)}]", True

        for root, _, files in os.walk(abs_path):
            if ".git" in root or "__pycache__" in root:
                continue
            for f in files:
                if include and not glob.fnmatch.fnmatch(f, include):
                    continue
                file_path = os.path.join(root, f)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
                        for idx, line in enumerate(fp, start=1):
                            if regex.search(line):
                                rel = os.path.relpath(file_path, self.workspace_root).replace("\\", "/")
                                results.append(f"{rel}:{idx}: {line.strip()}")
                                if len(results) >= 100:
                                    break
                except Exception:
                    continue
            if len(results) >= 100:
                break

        return "\n".join(results) if results else "No matches found.", False

    def _bash(self, command: str, timeout_seconds: int = 120, cwd: str = ".") -> Tuple[str, bool, Optional[str]]:
        allowed, err_msg = self.guard.check_shell_permission(command)
        if not allowed:
            return err_msg or "Command denied by permission policy", True, "PERMISSION_DENIED"

        abs_cwd = self.guard.canonicalize_path(cwd)
        try:
            res = subprocess.run(
                command,
                shell=True,
                cwd=abs_cwd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            stdout = res.stdout.strip()
            stderr = res.stderr.strip()
            exit_code = res.returncode
            output = f"[Exit Code: {exit_code}]\n"
            if stdout:
                output += f"STDOUT:\n{stdout}\n"
            if stderr:
                output += f"STDERR:\n{stderr}\n"

            # Novel Extension: Bash-Only + Diagnostics!
            # Inspect git diff --name-only to check if any Python file was mutated
            badge = None
            try:
                diff_res = subprocess.run(
                    ["git", "diff", "--name-only"],
                    cwd=self.workspace_root,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if diff_res.returncode == 0:
                    changed_files = [f.strip() for f in diff_res.stdout.splitlines() if f.strip().endswith(".py")]
                    for cf in changed_files:
                        full_cf = os.path.join(self.workspace_root, cf)
                        diag = self.guard.run_post_edit_diagnostics(full_cf)
                        if diag:
                            output += f"\n\n[AgentGuard Post-Bash Diagnostics on '{cf}']\n{diag}"
                            badge = "LINT_DETECTED"
            except Exception:
                pass

            return output, (exit_code != 0), badge
        except subprocess.TimeoutExpired:
            return f"[Error: Command timed out after {timeout_seconds} seconds]", True, None
        except Exception as e:
            return f"[Error executing bash command: {str(e)}]", True, None
