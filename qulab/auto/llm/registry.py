"""Provider registry for LLM providers."""

from typing import TYPE_CHECKING

from .base import LLMProvider
from .openai import OpenAIProvider

try:
    from .anthropic import AnthropicProvider

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

if TYPE_CHECKING:
    from ..config import LLMConfig


class ProviderRegistry:
    """Registry for LLM providers."""

    def __init__(self):
        """Initialize registry."""
        self._providers: dict[str, type[LLMProvider]] = {
            "openai": OpenAIProvider,
            "kimi": OpenAIProvider,  # Kimi uses OpenAI-compatible API
        }

        if HAS_ANTHROPIC:
            self._providers["anthropic"] = AnthropicProvider

    def register(self, name: str, provider_class: type[LLMProvider]) -> None:
        """Register a provider.

        Args:
            name: Provider name
            provider_class: Provider class
        """
        self._providers[name] = provider_class

    def create(self, config: "LLMConfig") -> LLMProvider:
        """Create a provider from config.

        Args:
            config: LLM configuration

        Returns:
            Configured LLM provider

        Raises:
            ValueError: If provider not found
        """
        provider_name = config.provider.lower()

        if provider_name not in self._providers:
            raise ValueError(f"Unknown provider: {provider_name}")

        provider_class = self._providers[provider_name]

        # Build kwargs from config
        kwargs = {
            "model": config.model,
        }

        if config.temperature is not None:
            kwargs["temperature"] = config.temperature

        if config.max_tokens is not None:
            kwargs["max_tokens"] = config.max_tokens

        # Add extra config parameters (provider-specific options)
        if config.extra:
            # Filter out internal parameters that shouldn't be passed to API
            internal_params = {"enable_thinking"}
            for key, value in config.extra.items():
                if key not in internal_params:
                    kwargs[key] = value

        # Add provider-specific arguments
        if provider_name in ("openai", "kimi"):
            if not config.base_url:
                raise ValueError(f"base_url is required for {provider_name} provider")
            if not config.api_key:
                raise ValueError(f"api_key is required for {provider_name} provider")

            return OpenAIProvider(
                base_url=config.base_url,
                api_key=config.api_key,
                **kwargs,
            )

        if provider_name == "anthropic":
            if not config.api_key:
                raise ValueError("api_key is required for anthropic provider")

            return AnthropicProvider(
                api_key=config.api_key,
                **kwargs,
            )

        # Generic instantiation
        return provider_class(**kwargs)

    def list_providers(self) -> list[str]:
        """List available provider names.

        Returns:
            List of provider names
        """
        return list(self._providers.keys())
