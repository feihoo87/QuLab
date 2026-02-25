"""Configuration management for auto experiment framework."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .llm.base import LLMProvider
from .llm.registry import ProviderRegistry


@dataclass
class LLMConfig:
    """LLM configuration."""

    provider: str  # "anthropic", "openai", "kimi"
    model: str
    base_url: str | None = None
    api_key: str | None = None
    temperature: float | None = 0.7
    max_tokens: int | None = 4096
    extra: dict = field(default_factory=dict)

    def create_provider(self) -> LLMProvider:
        """Create a provider instance from this config.

        Returns:
            Configured LLM provider
        """
        registry = ProviderRegistry()
        return registry.create(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LLMConfig":
        """Create from dictionary.

        Args:
            data: Configuration dict

        Returns:
            LLMConfig instance
        """
        return cls(
            provider=data.get("provider", "openai"),
            model=data.get("model", ""),
            base_url=data.get("base_url"),
            api_key=data.get("api_key"),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens", 4096),
            extra={k: v for k, v in data.items() if k not in {
                "provider", "model", "base_url", "api_key", "temperature", "max_tokens"
            }},
        )

    def to_dict(self) -> dict:
        """Convert to dictionary.

        Returns:
            Configuration dict
        """
        result = {
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            **self.extra,
        }
        if self.base_url is not None:
            result["base_url"] = self.base_url
        if self.api_key is not None:
            result["api_key"] = self.api_key
        return result


@dataclass
class AutoLabConfig:
    """AutoLab configuration."""

    llm: LLMConfig | None = None
    skills_paths: list[str] = field(default_factory=list)
    max_iterations: int = 40
    enable_thinking: bool = True
    custom_system_prompt: str | None = None
    auto_approve_configs: bool = False  # For testing - auto-approve config changes

    @classmethod
    def from_file(cls, path: str | Path) -> "AutoLabConfig":
        """Load from YAML file.

        Args:
            path: Path to config file

        Returns:
            AutoLabConfig instance
        """
        path = Path(path)
        if not path.exists():
            return cls()

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "AutoLabConfig":
        """Create from dictionary.

        Args:
            data: Configuration dict

        Returns:
            AutoLabConfig instance
        """
        llm_data = data.get("llm", {})
        llm_config = LLMConfig.from_dict(llm_data) if llm_data else None

        return cls(
            llm=llm_config,
            skills_paths=data.get("skills_paths", []),
            max_iterations=data.get("max_iterations", 40),
            enable_thinking=data.get("enable_thinking", True),
            custom_system_prompt=data.get("custom_system_prompt"),
            auto_approve_configs=data.get("auto_approve_configs", False),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary.

        Returns:
            Configuration dict
        """
        result = {
            "skills_paths": self.skills_paths,
            "max_iterations": self.max_iterations,
            "enable_thinking": self.enable_thinking,
            "auto_approve_configs": self.auto_approve_configs,
        }

        if self.llm:
            result["llm"] = {
                "provider": self.llm.provider,
                "model": self.llm.model,
                "base_url": self.llm.base_url,
                "api_key": self.llm.api_key,
                "temperature": self.llm.temperature,
                "max_tokens": self.llm.max_tokens,
                **self.llm.extra,
            }

        if self.custom_system_prompt:
            result["custom_system_prompt"] = self.custom_system_prompt

        return result

    def save(self, path: str | Path) -> None:
        """Save to YAML file.

        Args:
            path: Path to save to
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, allow_unicode=True)
