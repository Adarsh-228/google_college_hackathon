"""Terminal execution tool."""

import time
from typing import Any, Dict

from packages.harness_core.contracts.enums import ToolPermission
from packages.harness_core.contracts.responses import ToolExecutionResult
from packages.harness_core.tools.base import BaseTool, ToolContext


class RunTerminalCommandTool(BaseTool):
    """Executes a shell or CLI command inside the sandboxed workspace."""

    @property
    def name(self) -> str:
        return "run_terminal_command"

    @property
    def description(self) -> str:
        return "Run a shell command inside the workspace directory. Restricted execution runner."

    @property
    def permission(self) -> ToolPermission:
        return ToolPermission.EXECUTE_TERMINAL

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command line to execute inside the workspace.",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Execution timeout in seconds (default: 60).",
                },
            },
            "required": ["command"],
        }

    async def execute(
        self, arguments: Dict[str, Any], context: ToolContext
    ) -> ToolExecutionResult:
        start_t = time.perf_counter()
        command = arguments.get("command", "").strip()
        timeout_seconds = arguments.get("timeout_seconds", 60)

        if not command:
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error="Empty command provided.",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

        try:
            exit_code, stdout, stderr = await context.runner.run_command(
                command,
                cwd=context.workspace.root,
                timeout_seconds=timeout_seconds,
            )

            success = (exit_code == 0)
            formatted_output = f"Exit Code: {exit_code}\nStdout:\n{stdout}\n"
            if stderr:
                formatted_output += f"Stderr:\n{stderr}\n"

            return ToolExecutionResult(
                tool_name=self.name,
                success=success,
                output=formatted_output,
                error=stderr if not success else None,
                metadata={"exit_code": exit_code},
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolExecutionResult(
                tool_name=self.name,
                success=False,
                error=f"Command execution error: {str(e)}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )


# Aliases
RunTerminalTool = RunTerminalCommandTool
