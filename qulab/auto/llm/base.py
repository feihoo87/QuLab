"""LLM provider abstract base class."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ToolCall:
    """Tool call from LLM."""

    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    """LLM response."""

    content: str | None
    tool_calls: list[ToolCall]
    model: str
    usage: dict | None = None
    reasoning_content: str | None = None  # For models with thinking capability (e.g., Kimi)


class LLMProvider(ABC):
    """LLM provider abstract base class."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
    ) -> LLMResponse:
        """Send chat request to LLM.

        Args:
            messages: List of message dicts with role and content
            tools: Optional list of tool definitions for function calling
            tool_choice: Tool choice mode ("auto", "required", "none")

        Returns:
            LLMResponse with content and tool calls
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    def _format_tools(self, tools: list[dict] | None) -> list[dict] | None:
        """Format tools for the provider's API.

        Override if provider needs specific format.
        """
        return tools
