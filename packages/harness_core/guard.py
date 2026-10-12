import os
import ast
import hashlib
import json
import subprocess
from typing import Dict, Any, Optional, Tuple, List
from .types import HarnessConfig, CircuitBreakerError

class AgentGuard:
    """
    Substrate Safety & Integrity Gate for Coding Agents.
    Implements Read-Before-Write (RBW), Post-Edit Diagnostics, 
    Workspace Path Containment, and Streak Circuit Breaking.
    """

    def __init__(self, workspace_root: str, config: HarnessConfig):
        self.workspace_root = os.path.realpath(workspace_root)
        self.config = config
        
        # Session state for Read-Before-Write: path -> (sha256, is_full_read)
        self.session_file_state: Dict[str, Tuple[str, bool]] = {}
        
        # Streak detection state
        self.last_call_signature: Optional[str] = None
        self.current_streak: int = 0
        self.consecutive_failing_streak: int = 0
        self.warning_injected: bool = False

    def canonicalize_path(self, rel_path: str) -> str:
        """Resolves path and enforces containment inside workspace root (anti-symlink-escape)."""
        clean_rel = rel_path.strip().lstrip("/\\")
        target_path = os.path.realpath(os.path.join(self.workspace_root, clean_rel))
        
        # Enforce chroot/workspace confinement
        common = os.path.commonpath([self.workspace_root, target_path])
        if common != self.workspace_root:
            raise PermissionError(f"Access denied: path '{rel_path}' escapes workspace root '{self.workspace_root}'")
        return target_path

    def get_workspace_rel_path(self, abs_path: str) -> str:
        """Returns normalized relative path inside workspace."""
        return os.path.relpath(os.path.realpath(abs_path), self.workspace_root).replace("\\", "/")

    # -------------------------------------------------------------
    # Gate 1: Read-Before-Write (RBW)
    # -------------------------------------------------------------
    def record_read(self, abs_path: str, is_full_read: bool, content: str) -> None:
        """Records a read operation and its content hash in the session state."""
        if not self.config.enable_rbw:
            return
        rel = self.get_workspace_rel_path(abs_path)
        content_hash = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
        self.session_file_state[rel] = (content_hash, is_full_read)

    def validate_write_permission(self, abs_path: str, is_overwrite: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Validates if an edit/overwrite is permitted.
        Returns (is_allowed, error_message).
        """
        if not self.config.enable_rbw:
            return True, None

        rel = self.get_workspace_rel_path(abs_path)
        file_exists = os.path.exists(abs_path)

        if not file_exists:
            # Creating a new file does not require prior read
            return True, None

        # Existing file: MUST have been read fully in this session
        if rel not in self.session_file_state:
            return False, (
                f"[AgentGuard RBW: Rejected] File '{rel}' exists but has not been read in this session. "
                f"You MUST inspect it with read_file(path='{rel}') before editing or overwriting."
            )

        recorded_hash, is_full_read = self.session_file_state[rel]
        if not is_full_read:
            return False, (
                f"[AgentGuard RBW: Rejected] Only a partial read was recorded for '{rel}'. "
                f"You MUST call read_file with offset=1 covering the full file before mutating it."
            )

        # Check for external modification
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                current_content = f.read()
            current_hash = hashlib.sha256(current_content.encode("utf-8", errors="replace")).hexdigest()
            if current_hash != recorded_hash:
                return False, (
                    f"[AgentGuard RBW: Rejected] File '{rel}' was modified externally since your last read. "
                    f"Please read the latest content before making edits."
                )
        except Exception as e:
            return False, f"[AgentGuard RBW: Error] Failed reading file '{rel}': {str(e)}"

        return True, None

    def record_mutation(self, abs_path: str, new_content: str) -> None:
        """Updates hash state after an edit/write so immediate subsequent edits pass."""
        if not self.config.enable_rbw:
            return
        rel = self.get_workspace_rel_path(abs_path)
        new_hash = hashlib.sha256(new_content.encode("utf-8", errors="replace")).hexdigest()
        self.session_file_state[rel] = (new_hash, True)

    # -------------------------------------------------------------
    # Gate 2: Zero-Turn Post-Edit Diagnostics (Linter)
    # -------------------------------------------------------------
    def run_post_edit_diagnostics(self, abs_path: str) -> Optional[str]:
        """
        Runs instant read-only lint checks on a modified Python file.
        Returns concise findings string, or None if clean.
        """
        if not self.config.enable_lint or not abs_path.endswith(".py"):
            return None

        rel = self.get_workspace_rel_path(abs_path)
        if not os.path.exists(abs_path):
            return None

        # 1. Attempt ruff check
        try:
            res = subprocess.run(
                ["ruff", "check", abs_path, "--output-format=concise", "--select=E,F"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode != 0 and res.stdout.strip():
                # Clean up absolute paths for clean presentation
                clean_output = res.stdout.strip().replace(abs_path, rel)
                return f"[AgentGuard Linter: ruff]\n{clean_output}"
        except (FileNotFoundError, subprocess.SubprocessError):
            pass

        # 2. Fallback: ast.parse (Pure Python syntax check)
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()
            ast.parse(source, filename=rel)
        except SyntaxError as syn_err:
            return (
                f"[AgentGuard Linter: SyntaxError]\n"
                f"{rel}:{syn_err.lineno}:{syn_err.offset}: {syn_err.msg}\n"
                f"  {syn_err.text.strip() if syn_err.text else ''}"
            )
        except Exception as e:
            return f"[AgentGuard Linter: ParseError] {str(e)}"

        return None

    # -------------------------------------------------------------
    # Gate 3: Streak Circuit Breaker (Stuck Detection)
    # -------------------------------------------------------------
    def evaluate_streak(self, tool_name: str, args: Dict[str, Any], is_error: bool) -> Tuple[Optional[str], bool]:
        """
        Evaluates tool call repetition.
        Returns (warning_reminder_text, should_terminate).
        """
        if not self.config.enable_streak_breaker:
            return None, False

        signature = f"{tool_name}:{json.dumps(args, sort_keys=True)}"
        if signature == self.last_call_signature:
            self.current_streak += 1
            if is_error:
                self.consecutive_failing_streak += 1
            else:
                self.consecutive_failing_streak = 0
        else:
            self.last_call_signature = signature
            self.current_streak = 1
            self.consecutive_failing_streak = 1 if is_error else 0
            self.warning_injected = False

        # Termination threshold: 8 consecutive identical failing calls
        if self.consecutive_failing_streak >= 8:
            return (
                f"STUCK LOOP HALT: Called `{tool_name}` with identical arguments {self.consecutive_failing_streak} "
                f"consecutive times with repeated failure. Circuit breaker opened.",
                True,
            )

        # Warning threshold: 5 identical calls (any status) or 5 failing
        if (self.current_streak >= 5 or self.consecutive_failing_streak >= 5) and not self.warning_injected:
            self.warning_injected = True
            msg = (
                f"<system-reminder>\n"
                f"You have called `{tool_name}` with the EXACT SAME arguments {self.current_streak} times. "
                f"You are repeating actions without making forward progress. STOP — step back, inspect error "
                f"details or plan, and choose a DIFFERENT approach. Do NOT repeat the exact same call again.\n"
                f"</system-reminder>"
            )
            return msg, False

        return None, False

    # -------------------------------------------------------------
    # Permission Safety Gate (Shell Commands)
    # -------------------------------------------------------------
    def check_shell_permission(self, command: str) -> Tuple[bool, Optional[str]]:
        """Classifies shell operations into allow vs. deny list."""
        cmd = command.strip().lower()
        denied_patterns = ["rm -rf", "sudo ", "git push", "git reset --hard", "chmod -r", "chown -r"]
        for p in denied_patterns:
            if p in cmd:
                return False, f"[AgentGuard Permission: Denied] Command '{command}' contains disallowed destructive pattern '{p}'."
        return True, None
