"""Config tool for requesting configuration updates."""

from dataclasses import dataclass

from .base import BaseTool, ToolResult


@dataclass
class ConfigUpdateRequest(Exception):
    """Exception raised when config update is requested."""

    updates: dict
    reason: str

    def __str__(self) -> str:
        return f"Config update requested: {self.reason}"


class ConfigTool(BaseTool):
    """Request configuration updates."""

    name = "update_config"
    description = "Request an update to configuration parameters. The update will be applied after human confirmation."

    parameters = {
        "updates": {
            "type": "object",
            "description": "Configuration updates as key-value pairs",
            "required": True,
        },
        "reason": {
            "type": "string",
            "description": "Reason for the update",
            "required": True,
        },
    }

    async def execute(self, updates: dict, reason: str) -> ToolResult:
        """Execute config update request.

        Args:
            updates: Configuration updates
            reason: Update reason

        Returns:
            ToolResult (actually raises ConfigUpdateRequest for special handling)
        """
        # This tool doesn't complete normally - it raises an exception
        # that the agent loop handles by pausing for human confirmation
        raise ConfigUpdateRequest(updates, reason)
