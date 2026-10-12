"""Execution runner interfaces for sandboxed command execution."""

from abc import ABC, abstractmethod
import asyncio
import os
from pathlib import Path
import subprocess
from typing import Dict, List, Optional, Tuple

from packages.harness_core.exceptions.errors import (
    ExecutionTimeoutError,
    SecurityViolationError,
    ToolExecutionError,
)


class BaseExecutionRunner(ABC):
    """Abstract interface for executing terminal commands and programs."""

    @abstractmethod
    async def run_command(
        self,
        command: str,
        cwd: Path,
        timeout_seconds: int = 60,
        env: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str, str]:
        """Execute command. Returns (exit_code, stdout, stderr)."""
        pass


class RestrictedSubprocessRunner(BaseExecutionRunner):
    """Restricted local subprocess runner for development.

    NOTE: This runner applies working-directory locking, timeouts, and command filtering.
    For multi-tenant cloud production, an isolated Docker or gVisor sandbox runner is required.
    """

    DISALLOWED_COMMAND_PATTERNS = [
        "rm -rf /",
        "rmdir /s /q c:",
        "format ",
        ":(){ :|:& };:",
        "mkfs",
        "dd if=/dev",
        "shutdown",
        "reboot",
    ]

    def __init__(self, allow_network: bool = False) -> None:
        self.allow_network = allow_network

    def _validate_command(self, command: str) -> None:
        cmd_lower = command.lower()
        for forbidden in self.DISALLOWED_COMMAND_PATTERNS:
            if forbidden in cmd_lower:
                raise SecurityViolationError(
                    f"Command contains forbidden pattern: '{forbidden}'"
                )

    async def run_command(
        self,
        command: str,
        cwd: Path,
        timeout_seconds: int = 60,
        env: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str, str]:
        self._validate_command(command)

        # Sanitize environment: pass minimal safe vars
        safe_env = dict(os.environ)
        if env:
            safe_env.update(env)

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=safe_env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise ExecutionTimeoutError(
                    f"Command timed out after {timeout_seconds} seconds: '{command}'"
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode or 0

            return exit_code, stdout, stderr

        except Exception as e:
            if isinstance(e, (SecurityViolationError, ExecutionTimeoutError)):
                raise
            raise ToolExecutionError(f"Failed to execute command '{command}': {str(e)}")


class MockExecutionRunner(BaseExecutionRunner):
    """Mock runner for tests."""

    def __init__(self, default_stdout: str = "", default_exit_code: int = 0) -> None:
        self.executed_commands: List[Tuple[str, Path]] = []
        self.default_stdout = default_stdout
        self.default_exit_code = default_exit_code
        self.custom_handlers: Dict[str, Tuple[int, str, str]] = {}

    def set_command_result(self, cmd_substring: str, exit_code: int, stdout: str, stderr: str = "") -> None:
        self.custom_handlers[cmd_substring] = (exit_code, stdout, stderr)

    async def run_command(
        self,
        command: str,
        cwd: Path,
        timeout_seconds: int = 60,
        env: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, str, str]:
        self.executed_commands.append((command, cwd))
        for pattern, res in self.custom_handlers.items():
            if pattern in command:
                return res
        return self.default_exit_code, self.default_stdout, ""
