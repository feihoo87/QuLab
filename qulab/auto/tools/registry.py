"""Tool registry for managing and executing tools."""

from typing import TYPE_CHECKING

from qulab.storage import Storage

from .base import BaseTool, ToolResult

if TYPE_CHECKING:
    from ..config import LLMConfig
    from ..skills.loader import SkillLoader


class ToolRegistry:
    """Registry for tools available to the agent."""

    def __init__(
        self,
        storage: Storage,
        skill_loader: "SkillLoader",
        llm_config: "LLMConfig | None" = None,
    ):
        """Initialize tool registry.

        Args:
            storage: Storage instance for data access
            skill_loader: Skill loader for skill execution
            llm_config: Optional LLM configuration
        """
        self.storage = storage
        self.skill_loader = skill_loader
        self.llm_config = llm_config
        self._tools: dict[str, BaseTool] = {}

        self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """Register built-in tools."""
        from .analysis import AnalysisTool
        from .config import ConfigTool
        from .human import HumanQueryTool
        from .measurement import MeasurementTool
        from .query import QueryTool

        self.register(QueryTool(self.storage))
        self.register(MeasurementTool(self.storage, self.skill_loader))
        self.register(AnalysisTool(self.storage, self.skill_loader))
        self.register(ConfigTool())
        self.register(HumanQueryTool())

    def register(self, tool: BaseTool) -> None:
        """Register a tool.

        Args:
            tool: Tool instance to register
        """
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Unregister a tool.

        Args:
            name: Tool name
        """
        if name in self._tools:
            del self._tools[name]

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None
        """
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """List available tool names.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def get_definitions(self) -> list[dict]:
        """Get tool definitions for LLM function calling.

        Returns:
            List of tool definitions
        """
        return [tool.to_definition() for tool in self._tools.values()]

    async def execute(self, name: str, arguments: dict) -> ToolResult:
        """Execute a tool.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            ToolResult with execution result
        """
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(error=f"Unknown tool: {name}")

        # Validate arguments
        errors = tool.validate_args(arguments)
        if errors:
            return ToolResult(error=f"Validation errors: {', '.join(errors)}")

        # Execute tool
        try:
            return await tool.execute(**arguments)
        except Exception as e:
            return ToolResult(error=f"Execution error: {str(e)}")
