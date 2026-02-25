"""OpenAI-compatible API provider (supports Kimi, etc.)."""

import json
import uuid
from typing import Any

from .base import LLMProvider, LLMResponse, ToolCall


try:
    from openai import AsyncOpenAI

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    AsyncOpenAI = None


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible API provider (supports Kimi, etc.)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        **kwargs,
    ):
        """Initialize OpenAI-compatible provider.

        Args:
            base_url: API base URL (e.g., "https://api.moonshot.cn/v1")
            api_key: API key
            model: Model name (e.g., "kimi-k2.5")
            **kwargs: Additional options like temperature, max_tokens
        """
        if not HAS_OPENAI:
            raise ImportError(
                "openai package is required for OpenAIProvider. "
                "Install with: pip install openai"
            )

        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.kwargs = kwargs  # temperature, max_tokens, etc.

    @property
    def name(self) -> str:
        """Provider name."""
        return f"openai:{self.model}"

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
        # Prepare request arguments
        request_args = {
            "model": self.model,
            "messages": messages,
            **self.kwargs,
        }

        # Add tools if provided
        if tools:
            request_args["tools"] = tools
            if tool_choice != "auto":
                request_args["tool_choice"] = tool_choice

        # Make API call
        response = await self.client.chat.completions.create(**request_args)

        # Parse response
        choice = response.choices[0]
        message = choice.message

        # Extract tool calls
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    arguments = {"raw": tc.function.arguments}

                tool_calls.append(
                    ToolCall(
                        id=tc.id or str(uuid.uuid4()),
                        name=tc.function.name,
                        arguments=arguments,
                    )
                )

        # Extract usage
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            model=response.model or self.model,
            usage=usage,
        )

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse API response to LLMResponse.

        Args:
            response: Raw API response

        Returns:
            Parsed LLMResponse
        """
        choice = response.choices[0]
        message = choice.message

        # Extract tool calls
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    arguments = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    arguments = {"raw": tc.function.arguments}

                tool_calls.append(
                    ToolCall(
                        id=tc.id or str(uuid.uuid4()),
                        name=tc.function.name,
                        arguments=arguments,
                    )
                )

        # Extract usage
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            model=response.model or self.model,
            usage=usage,
        )
