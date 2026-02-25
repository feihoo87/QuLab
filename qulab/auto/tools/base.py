"""Base classes for tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolResult:
    """Result of a tool execution."""

    data: dict | None = None
    error: str | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Check if execution was successful."""
        return self.error is None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }


class BaseTool(ABC):
    """Base class for all tools."""

    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool.

        Args:
            **kwargs: Tool parameters

        Returns:
            ToolResult with execution result
        """
        pass

    def to_definition(self) -> dict:
        """Convert to OpenAI function calling format.

        Returns:
            Tool definition for LLM
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": [
                        name for name, param in self.parameters.items()
                        if param.get("required", False)
                    ],
                },
            },
        }

    def validate_args(self, arguments: dict) -> list[str]:
        """Validate tool arguments.

        Args:
            arguments: Arguments to validate

        Returns:
            List of validation errors
        """
        errors = []

        for name, param in self.parameters.items():
            if param.get("required", False) and name not in arguments:
                errors.append(f"Missing required parameter: {name}")

            if name in arguments:
                value = arguments[name]
                param_type = param.get("type")

                if param_type == "string" and not isinstance(value, str):
                    errors.append(f"Parameter {name} must be a string")
                elif param_type == "integer" and not isinstance(value, int):
                    errors.append(f"Parameter {name} must be an integer")
                elif param_type == "number" and not isinstance(value, (int, float)):
                    errors.append(f"Parameter {name} must be a number")
                elif param_type == "array" and not isinstance(value, list):
                    errors.append(f"Parameter {name} must be an array")
                elif param_type == "object" and not isinstance(value, dict):
                    errors.append(f"Parameter {name} must be an object")

        return errors
