"""Skill base class and data structures."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SkillInput:
    """Skill input parameter definition."""

    name: str
    param_type: str
    description: str
    default: Any = None
    required: bool = True


@dataclass
class SkillOutput:
    """Skill output definition."""

    name: str
    param_type: str
    description: str


@dataclass
class Skill:
    """Skill definition.

    A skill describes an experiment or analysis method with:
    - Metadata (name, type, description, capabilities)
    - Input/output parameter definitions
    - Execution code
    """

    name: str
    type: str  # "measurement" or "analysis"
    description: str
    capabilities: dict
    inputs: list[dict]
    outputs: list[dict]
    metadata: dict
    code: str  # Execution code
    filepath: Path | None = None

    def to_prompt(self) -> str:
        """Convert to LLM prompt format.

        Returns:
            Formatted skill description for LLM context
        """
        lines = [
            f"## {self.name}",
            "",
            f"**Type**: {self.type}",
            f"**Description**: {self.description}",
            "",
            "**Capabilities**:",
        ]

        # Format capabilities
        for category, items in self.capabilities.items():
            lines.append(f"- {category}:")
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        for key, value in item.items():
                            lines.append(f"  - {key}: {value}")
                    else:
                        lines.append(f"  - {item}")
            elif isinstance(items, dict):
                for key, value in items.items():
                    lines.append(f"  - {key}: {value}")

        lines.extend(["", "**Inputs**:", ""])
        for inp in self.inputs:
            name = inp.get("name", "unknown")
            param_type = inp.get("type", "any")
            description = inp.get("description", "")
            default = inp.get("default", None)

            if default is not None:
                lines.append(f"- {name} ({param_type}, default: {default}): {description}")
            else:
                lines.append(f"- {name} ({param_type}): {description}")

        lines.extend(["", "**Outputs**:", ""])
        for out in self.outputs:
            name = out.get("name", "unknown")
            param_type = out.get("type", "any")
            description = out.get("description", "")
            lines.append(f"- {name} ({param_type}): {description}")

        if self.metadata:
            lines.extend(["", "**Metadata**:", ""])
            for key, value in self.metadata.items():
                lines.append(f"- {key}: {value}")

        return "\n".join(lines)

    def get_input(self, name: str) -> dict | None:
        """Get input parameter by name.

        Args:
            name: Parameter name

        Returns:
            Input definition or None
        """
        for inp in self.inputs:
            if inp.get("name") == name:
                return inp
        return None

    def get_output(self, name: str) -> dict | None:
        """Get output parameter by name.

        Args:
            name: Parameter name

        Returns:
            Output definition or None
        """
        for out in self.outputs:
            if out.get("name") == name:
                return out
        return None

    def validate_inputs(self, parameters: dict) -> list[str]:
        """Validate input parameters.

        Args:
            parameters: Parameters to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        for inp in self.inputs:
            name = inp.get("name", "")
            required = inp.get("required", True)
            default = inp.get("default", None)

            if name not in parameters:
                if required and default is None:
                    errors.append(f"Missing required parameter: {name}")

        return errors
