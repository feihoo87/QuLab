"""Human query tool for asking humans."""

from dataclasses import dataclass

from .base import BaseTool, ToolResult


@dataclass
class HumanInterruption(Exception):
    """Exception raised when human input is needed."""

    question: str
    options: list[str] | None
    context: dict | None

    def __str__(self) -> str:
        return f"Human input needed: {self.question}"


class HumanQueryTool(BaseTool):
    """Ask human for input or confirmation."""

    name = "ask_human"
    description = "Ask the human operator a question or request confirmation. Use this when uncertain or when human approval is needed."

    parameters = {
        "question": {
            "type": "string",
            "description": "The question to ask the human",
            "required": True,
        },
        "options": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional list of choices for the human",
        },
        "context": {
            "type": "object",
            "description": "Additional context to help the human understand the question",
        },
    }

    async def execute(
        self,
        question: str,
        options: list[str] | None = None,
        context: dict | None = None,
    ) -> ToolResult:
        """Execute human query.

        Args:
            question: Question to ask
            options: Optional choices
            context: Additional context

        Returns:
            ToolResult (actually raises HumanInterruption for special handling)
        """
        # This tool doesn't complete normally - it raises an exception
        # that the agent loop handles by pausing for human response
        raise HumanInterruption(question, options, context)
