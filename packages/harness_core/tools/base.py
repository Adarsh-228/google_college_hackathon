"""Base tool definition and tool context."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field

from packages.harness_core.contracts.enums import ToolPermission
from packages.harness_core.contracts.responses import ToolExecutionResult
from packages.harness_core.execution.runner import BaseExecutionRunner
from packages.harness_core.execution.workspace import WorkspaceManager


class ToolContext(BaseModel):
    """Runtime context provided to tool execution."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: str
    step_index: int = 0
    workspace: WorkspaceManager
    runner: BaseExecutionRunner


class BaseTool(ABC):
    """Abstract base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Clear documentation of tool purpose and usage."""
        pass

    @property
    @abstractmethod
    def permission(self) -> ToolPermission:
        """Permission requirement."""
        pass

    @property
    @abstractmethod
    def parameters_schema(self) -> Dict[str, Any]:
        """JSON Schema defining input parameters."""
        pass

    @abstractmethod
    async def execute(
        self,
        arguments: Dict[str, Any],
        context: ToolContext,
    ) -> ToolExecutionResult:
        """Execute tool and return structured ToolExecutionResult."""
        pass

    def to_gemini_declaration(self) -> Dict[str, Any]:
        """Format as Gemini functionDeclaration dict."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters_schema,
        }
