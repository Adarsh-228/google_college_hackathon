"""AgentGuard central interception layer coordinating all 7 safety modules."""

import logging
from typing import Any, Callable, Dict, Optional

from packages.harness_core.config.settings import EngineConfig
from packages.harness_core.contracts.enums import HarnessMode
from packages.harness_core.contracts.requests import ToolExecutionRequest
from packages.harness_core.contracts.responses import ToolExecutionResult
from packages.harness_core.exceptions.errors import GuardViolationError
from packages.harness_core.execution.workspace import WorkspaceManager
from packages.harness_core.guard.circuit_breaker import CircuitBreaker, ExecutionLimitManager
from packages.harness_core.guard.diagnostics import CodeDiagnosticsGuard, PostEditDiagnostics
from packages.harness_core.guard.file_integrity import (
    FileIntegrityGuard,
    FileStateValidator,
    ReadBeforeWriteValidator,
)
from packages.harness_core.guard.loop_detector import LoopDetector, RepeatedCallDetector
from packages.harness_core.guard.permission_manager import PermissionManager
from packages.harness_core.guard.workspace_protection import WorkspaceProtection
from packages.harness_core.tools.base import BaseTool, ToolContext

logger = logging.getLogger(__name__)


class AgentGuard:
    """Central safety interceptor coordinating state validation, integrity, loops, and limits."""

    def __init__(
        self,
        workspace: WorkspaceManager,
        config: Optional[EngineConfig] = None,
        on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        harness_mode: HarnessMode = HarnessMode.HYBRID,
    ) -> None:
        self.workspace = workspace
        self.config = config or EngineConfig()
        self.on_event = on_event
        self.harness_mode = harness_mode

        # The 7 Core Guard Subsystems
        self.file_state_validator = FileStateValidator(workspace)
        self.read_before_write_validator = ReadBeforeWriteValidator(workspace)
        self.diagnostics = PostEditDiagnostics(
            workspace=workspace,
            enable_ruff=self.config.enable_ruff,
        )
        self.loop_detector = RepeatedCallDetector(
            warning_threshold=self.config.guard_max_loop_attempts,
            stall_threshold=self.config.guard_max_failed_repeats,
        )
        self.limit_manager = ExecutionLimitManager(
            max_tool_calls=self.config.guard_max_tool_calls,
            timeout_seconds=self.config.guard_timeout_seconds,
        )
        self.workspace_protection = WorkspaceProtection(workspace)
        self.permission_manager = PermissionManager()

        # Backward compatibility aliases
        self.file_integrity = self.read_before_write_validator
        self.circuit_breaker = self.limit_manager

    async def execute_guarded(
        self,
        request: ToolExecutionRequest,
        tool: BaseTool,
        context: ToolContext,
    ) -> ToolExecutionResult:
        """Safely intercept and execute a tool call with pre/post verifications."""
        # 1. Execution Limit Check
        self.limit_manager.record_tool_call()

        # 2. Permission Policy Check
        permitted, perm_reason = self.permission_manager.check_permission(
            tool.permission, self.harness_mode
        )
        if not permitted:
            logger.warning(f"AgentGuard permission denied: {perm_reason}")
            return ToolExecutionResult(
                tool_name=tool.name,
                success=False,
                error=perm_reason,
                metadata={"guard_blocked": True, "reason": "permission_denied"},
            )

        # 3. Workspace Boundary Validation for file paths
        file_arg = request.arguments.get("file_path") or request.arguments.get("directory_path")
        if file_arg:
            is_safe, escape_reason = self.workspace_protection.validate_path(str(file_arg))
            if not is_safe:
                logger.warning(f"AgentGuard blocked workspace escape attempt: {escape_reason}")
                return ToolExecutionResult(
                    tool_name=tool.name,
                    success=False,
                    error=escape_reason,
                    metadata={"guard_blocked": True, "reason": "workspace_escape"},
                )

        # 4. Read-Before-Write Integrity Pre-check
        if tool.name in ("write_file", "edit_file"):
            file_p = str(request.arguments.get("file_path", ""))
            is_valid, integrity_reason = self.read_before_write_validator.validate_pre_modification(file_p)
            if not is_valid:
                logger.warning(f"AgentGuard blocked modification on '{file_p}': {integrity_reason}")
                return ToolExecutionResult(
                    tool_name=tool.name,
                    success=False,
                    error=integrity_reason,
                    metadata={"guard_blocked": True, "reason": "integrity_violation"},
                )

        # 5. Execute Tool
        result = await tool.execute(request.arguments, context)

        # 6. Post-Edit Code Diagnostics
        for touched_file in result.files_touched:
            if touched_file.endswith(".py"):
                diags = self.diagnostics.check_file(touched_file)
                if diags:
                    result.diagnostics.extend(diags)
                    logger.info(
                        f"AgentGuard captured {len(diags)} diagnostic(s) on '{touched_file}'"
                    )

        # 7. Repeated Call & Loop Detection
        loop_status = self.loop_detector.record_call(
            tool_name=tool.name,
            arguments=request.arguments,
            success=result.success,
        )
        if loop_status.is_warning and loop_status.message:
            result.metadata["loop_warning"] = loop_status.message
            if self.on_event:
                self.on_event("loop_warning", {"message": loop_status.message})

        return result
