"""Anthropic Claude provider."""

import uuid
from typing import Any

from .base import LLMProvider, LLMResponse, ToolCall


try:
    from anthropic import AsyncAnthropic

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False
    AsyncAnthropic = None


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-sonnet-20240229",
        **kwargs,
    ):
        """Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key
            model: Model name
            **kwargs: Additional options like temperature, max_tokens
        """
        if not HAS_ANTHROPIC:
            raise ImportError(
                "anthropic package is required for AnthropicProvider. "
                "Install with: pip install anthropic"
            )

        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.kwargs = kwargs

    @property
    def name(self) -> str:
        """Provider name."""
        return f"anthropic:{self.model}"

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
    ) -> LLMResponse:
        """Send chat request.

        Args:
            messages: List of message dicts
            tools: Optional tool definitions
            tool_choice: Tool choice mode

        Returns:
            LLMResponse with content and tool calls
        """
        # Convert messages to Anthropic format
        system_message = None
        chat_messages = []

        for msg in messages:
            if msg.get("role") == "system":
                system_message = msg.get("content", "")
            elif msg.get("role") == "tool":
                # Tool results go in user messages with tool_result blocks
                chat_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", ""),
                        "content": msg.get("content", ""),
                    }],
                })
            else:
                chat_messages.append(msg)

        # Prepare request arguments
        request_args = {
            "model": self.model,
            "messages": chat_messages,
            "max_tokens": self.kwargs.get("max_tokens", 4096),
        }

        if system_message:
            request_args["system"] = system_message

        if "temperature" in self.kwargs:
            request_args["temperature"] = self.kwargs["temperature"]

        # Convert tools to Anthropic format if provided
        if tools:
            anthropic_tools = self._convert_tools(tools)
            request_args["tools"] = anthropic_tools

            if tool_choice == "required":
                request_args["tool_choice"] = {"type": "any"}
            elif tool_choice == "none":
                request_args["tool_choice"] = {"type": "none"}

        # Make API call
        response = await self.client.messages.create(**request_args)

        # Parse response
        return self._parse_response(response)

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """Convert OpenAI-style tools to Anthropic format.

        Args:
            tools: OpenAI-style tool definitions

        Returns:
            Anthropic-style tool definitions
        """
        anthropic_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                anthropic_tools.append({
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {}),
                })
        return anthropic_tools

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse Anthropic response to LLMResponse.

        Args:
            response: Raw Anthropic response

        Returns:
            Parsed LLMResponse
        """
        content_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id or str(uuid.uuid4()),
                        name=block.name,
                        arguments=block.input if isinstance(block.input, dict) else {},
                    )
                )

        # Extract usage
        usage = None
        if hasattr(response, "usage"):
            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            }

        return LLMResponse(
            content="\n".join(content_parts) if content_parts else None,
            tool_calls=tool_calls,
            model=response.model or self.model,
            usage=usage,
        )
