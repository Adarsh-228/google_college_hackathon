"""Permission manager enforcing access control policies on agent tools."""

from typing import Optional, Set, Tuple
from packages.harness_core.contracts.enums import HarnessMode, ToolPermission


class PermissionManager:
    """Evaluates whether an requested tool execution is allowed under current policy and mode."""

    def __init__(
        self,
        disallowed_permissions: Optional[Set[ToolPermission]] = None,
        read_only_mode: bool = False,
    ) -> None:
        self.disallowed_permissions = disallowed_permissions or set()
        self.read_only_mode = read_only_mode

    def check_permission(
        self,
        tool_permission: ToolPermission,
        harness_mode: HarnessMode = HarnessMode.HYBRID,
    ) -> Tuple[bool, Optional[str]]:
        """Validate if tool permission is granted.

        Returns (is_allowed, denial_reason).
        """
        # 1. Global read-only enforcement
        if self.read_only_mode and tool_permission != ToolPermission.READ_ONLY:
            return False, f"Permission Denied: Agent is operating in strict read-only mode. '{tool_permission.value}' not allowed."

        # 2. Explicitly disallowed permissions
        if tool_permission in self.disallowed_permissions:
            return False, f"Permission Denied: Permission '{tool_permission.value}' is explicitly blocked by policy."

        # 3. Harness Mode restrictions
        if harness_mode == HarnessMode.GUIDED:
            if tool_permission == ToolPermission.EXECUTE_TERMINAL:
                return (
                    False,
                    "Permission Denied: Terminal execution is disabled in GUIDED mode. Use file manipulation tools.",
                )

        return True, None
