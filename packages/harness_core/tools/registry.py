"""Tool Registry for managing and declaring agent tools."""

from typing import Any, Dict, List, Optional

from packages.harness_core.contracts.enums import HarnessMode, ToolPermission
from packages.harness_core.tools.base import BaseTool
from packages.harness_core.tools.file_tools import (
    EditFileTool,
    ListFilesTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)
from packages.harness_core.tools.terminal_tools import RunTerminalCommandTool


class ToolRegistry:
    """Registry maintaining available tools and providing schema exports."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a new tool instance."""
        self._tools[tool.name] = tool

    def unregister(self, tool_name: str) -> None:
        """Remove a tool from registry."""
        self._tools.pop(tool_name, None)

    ALIAS_MAP = {
        "list_directory": "list_files",
        "run_terminal": "run_terminal_command",
    }

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Lookup tool by name or alias."""
        clean_name = name.strip() if name else ""
        resolved_name = self.ALIAS_MAP.get(clean_name, clean_name)
        return self._tools.get(resolved_name)

    def list_tools(self) -> List[BaseTool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def get_tools_for_mode(self, mode: HarnessMode) -> List[BaseTool]:
        """Filter tools appropriate for the chosen harness mode."""
        if mode == HarnessMode.GUIDED:
            # GUIDED: File tools only (explicit, structured edits)
            return [
                t for t in self._tools.values()
                if t.permission in (ToolPermission.READ_ONLY, ToolPermission.WRITE_FILE)
            ]
        elif mode == HarnessMode.DIRECT:
            # DIRECT: Terminal tool focused with basic inspection
            return [
                t for t in self._tools.values()
                if t.name in ("run_terminal_command", "list_files", "read_file")
            ]
        else:
            # HYBRID: All registered tools
            return list(self._tools.values())

    def export_schemas_for_mode(self, mode: HarnessMode) -> List[Dict[str, Any]]:
        """Export tool parameter schemas for LLM consumption."""
        tools = self.get_tools_for_mode(mode)
        return [t.to_gemini_declaration() for t in tools]

    @classmethod
    def create_default(cls) -> "ToolRegistry":
        """Instantiate registry populated with all standard HarnessX tools."""
        registry = cls()
        registry.register(ReadFileTool())
        registry.register(WriteFileTool())
        registry.register(EditFileTool())
        registry.register(ListFilesTool())
        registry.register(SearchFilesTool())
        registry.register(RunTerminalCommandTool())
        return registry
