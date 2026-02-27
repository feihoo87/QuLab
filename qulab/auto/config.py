"""Configuration management for auto experiment framework using Pydantic v2."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class LLMConfig(BaseModel):
    """LLM configuration with Pydantic v2 validation.

    Attributes:
        provider: LLM provider name (anthropic, openai, kimi)
        model: Model name to use
        base_url: Optional API base URL
        api_key: Optional API key (falls back to env vars)
        temperature: Sampling temperature (0-2)
        max_tokens: Maximum tokens to generate
        timeout: Request timeout in seconds
    """

    model_config = ConfigDict(
        validate_assignment=True,
        extra="allow",
    )

    provider: Literal["anthropic", "openai", "kimi", "deepseek"] = "openai"
    model: str = ""
    base_url: str | None = None
    api_key: str | None = None
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int | None = Field(default=4096, gt=0)
    timeout: float = Field(default=120.0, gt=0)

    @field_validator("api_key", mode="before")
    @classmethod
    def _resolve_api_key(cls, v: str | None, info) -> str | None:
        """Resolve API key from environment variables if not provided."""
        if v is not None:
            return v

        # Map providers to their environment variable names
        env_vars = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "kimi": "KIMI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
        }

        provider = info.data.get("provider", "openai")
        env_var = env_vars.get(provider)
        if env_var:
            return os.environ.get(env_var)
        return None

    @property
    def extra(self) -> dict[str, Any]:
        """Backward compatibility property for extra fields.

        Returns:
            Dictionary of extra fields not in the main schema
        """
        # Get all model fields from the class
        from pydantic import BaseModel
        known_fields = set(self.__class__.model_fields.keys())
        # Get all current values
        all_values = self.model_dump()
        # Return only non-None values for unknown fields
        return {
            k: v for k, v in all_values.items()
            if k not in known_fields and v is not None
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LLMConfig":
        """Create from dictionary (backward compatibility).

        Args:
            data: Configuration dict

        Returns:
            LLMConfig instance
        """
        return cls.model_validate(data)

    def to_dict(self) -> dict:
        """Convert to dictionary (backward compatibility).

        Returns:
            Configuration dict
        """
        return self.model_dump()

    def create_provider(self):
        """Create a provider instance from this config.

        Returns:
            Configured LLM provider
        """
        # Import here to avoid circular imports
        from .llm.registry import ProviderRegistry

        registry = ProviderRegistry()
        return registry.create(self)


class SkillConfig(BaseModel):
    """Skill system configuration.

    Attributes:
        paths: List of paths to search for skills
        cache_dir: Directory for caching generated code
        max_retries: Maximum number of retries for code generation
        force_regenerate: Force regeneration of code (for debugging)
        hot_reload: Enable hot reload of skills during development
    """

    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
    )

    paths: list[str] = Field(default_factory=list)
    cache_dir: str = "~/.qulab/skill_cache"
    max_retries: int = Field(default=3, ge=0, le=10)
    force_regenerate: bool = False
    hot_reload: bool = False

    @field_validator("cache_dir")
    @classmethod
    def _expand_cache_dir(cls, v: str) -> str:
        """Expand user home directory in cache_dir."""
        return os.path.expanduser(v)


class ExecutorConfig(BaseModel):
    """Code executor configuration.

    Attributes:
        max_execution_time: Maximum execution time in seconds
        enable_retry: Whether to enable retry on failure
        max_retry_count: Maximum number of retries
        safe_mode: Whether to run in safe mode with restrictions
    """

    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
    )

    max_execution_time: float = Field(default=600.0, gt=0)
    enable_retry: bool = True
    max_retry_count: int = Field(default=3, ge=0, le=10)
    safe_mode: bool = False


class MemoryConfig(BaseModel):
    """Memory system configuration.

    Attributes:
        window_size: Number of recent messages to keep in context
        consolidation_threshold: Threshold for triggering memory consolidation
        enable_consolidation: Whether to enable automatic memory consolidation
    """

    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
    )

    window_size: int = Field(default=20, ge=5, le=100)
    consolidation_threshold: int = Field(default=50, ge=20, le=200)
    enable_consolidation: bool = True


class WorldModelConfig(BaseModel):
    """World Model configuration.

    Attributes:
        auto_save: Whether to auto-save parameter changes
        parameter_ttl: Default TTL for parameters in seconds
        enable_history: Whether to track parameter history
    """

    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
    )

    auto_save: bool = True
    parameter_ttl: float | None = Field(default=86400.0, gt=0)  # 24 hours
    enable_history: bool = True


class BusConfig(BaseModel):
    """Message bus configuration.

    Attributes:
        enable_events: Whether to emit events during execution
        queue_size: Maximum size of the event queue
    """

    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
    )

    enable_events: bool = True
    queue_size: int = Field(default=1000, ge=100)


class AutoLabConfig(BaseModel):
    """AutoLab main configuration using Pydantic v2.

    This is the root configuration class that contains all sub-configurations.
    Supports loading from YAML files and environment variables.

    Attributes:
        llm: LLM configuration
        skills: Skill system configuration
        executor: Code executor configuration
        memory: Memory system configuration
        world_model: World Model configuration
        bus: Message bus configuration
        max_iterations: Maximum number of agent iterations
        enable_thinking: Whether to enable thinking mode
        custom_system_prompt: Custom system prompt to prepend
        auto_approve_configs: Auto-approve config changes (for testing)
    """

    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
        populate_by_name=True,
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    skills: SkillConfig = Field(default_factory=SkillConfig)
    executor: ExecutorConfig = Field(default_factory=ExecutorConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    world_model: WorldModelConfig = Field(default_factory=WorldModelConfig)
    bus: BusConfig = Field(default_factory=BusConfig)

    max_iterations: int = Field(default=40, ge=1, le=1000)
    enable_thinking: bool = True
    custom_system_prompt: str | None = None
    auto_approve_configs: bool = False

    @classmethod
    def from_file(cls, path: str | Path) -> AutoLabConfig:
        """Load configuration from YAML file.

        Args:
            path: Path to YAML config file

        Returns:
            AutoLabConfig instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file contains invalid config
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # Backward compatibility: handle old config format
        # Old format has skills_paths at top level, new format has it under skills
        if "skills_paths" in data and "skills" not in data:
            data["skills"] = {"paths": data.pop("skills_paths")}

        # Old format has skill_* at top level
        skill_config = data.get("skills", {})
        for old_key in ["skill_cache_dir", "skill_max_retries", "skill_force_regenerate"]:
            if old_key in data:
                new_key = old_key.replace("skill_", "")
                if new_key not in skill_config:
                    skill_config[new_key] = data.pop(old_key)
        if skill_config:
            data["skills"] = skill_config

        return cls.model_validate(data)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> AutoLabConfig:
        """Load configuration from YAML string.

        Args:
            yaml_str: YAML configuration string

        Returns:
            AutoLabConfig instance
        """
        data = yaml.safe_load(yaml_str) or {}
        return cls.model_validate(data)

    def to_yaml(self) -> str:
        """Convert configuration to YAML string.

        Returns:
            YAML formatted configuration string
        """
        return yaml.dump(
            self.model_dump(exclude_none=True),
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    def save(self, path: str | Path) -> None:
        """Save configuration to YAML file.

        Args:
            path: Path to save configuration to
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_yaml())

    def model_dump_legacy(self) -> dict[str, Any]:
        """Dump to legacy dictionary format for backwards compatibility.

        Returns:
            Dictionary in legacy format
        """
        # Access attributes directly - cast to dict to avoid pylint issues
        llm_config: LLMConfig = self.llm  # type: ignore
        skills_config: SkillConfig = self.skills  # type: ignore

        llm_data = llm_config.model_dump() if llm_config else {}  # pylint: disable=no-member
        skills_data = skills_config.model_dump() if skills_config else {}  # pylint: disable=no-member

        return {
            "llm": {
                "provider": llm_data.get("provider"),
                "model": llm_data.get("model"),
                "base_url": llm_data.get("base_url"),
                "api_key": llm_data.get("api_key"),
                "temperature": llm_data.get("temperature"),
                "max_tokens": llm_data.get("max_tokens"),
                "timeout": llm_data.get("timeout"),
            },
            "skills_paths": skills_data.get("paths", []),
            "max_iterations": self.max_iterations,
            "enable_thinking": self.enable_thinking,
            "custom_system_prompt": self.custom_system_prompt,
            "auto_approve_configs": self.auto_approve_configs,
            "skill_cache_dir": skills_data.get("cache_dir"),
            "skill_max_retries": skills_data.get("max_retries"),
            "skill_force_regenerate": skills_data.get("force_regenerate"),
        }

    # Backward compatibility properties
    @property
    def skills_paths(self) -> list[str]:
        """Backward compatibility for skills_paths."""
        return self.skills.paths if self.skills else []

    @skills_paths.setter
    def skills_paths(self, value: list[str]) -> None:
        """Set skills_paths (creates SkillConfig if needed)."""
        if self.skills is None:
            self.skills = SkillConfig()
        self.skills.paths = value

    @property
    def skill_cache_dir(self) -> str:
        """Backward compatibility for skill_cache_dir."""
        return self.skills.cache_dir if self.skills else "~/.qulab/skill_cache"

    @property
    def skill_max_retries(self) -> int:
        """Backward compatibility for skill_max_retries."""
        return self.skills.max_retries if self.skills else 3

    @property
    def skill_force_regenerate(self) -> bool:
        """Backward compatibility for skill_force_regenerate."""
        return self.skills.force_regenerate if self.skills else False

    @classmethod
    def from_dict(cls, data: dict) -> "AutoLabConfig":
        """Create from dictionary (backward compatibility).

        Args:
            data: Configuration dict

        Returns:
            AutoLabConfig instance
        """
        # Handle old config format migration
        data = dict(data)  # Make a copy to avoid modifying input

        # Backward compatibility: handle old config format
        if "skills_paths" in data and "skills" not in data:
            data["skills"] = {"paths": data.pop("skills_paths")}

        # Old format has skill_* at top level
        skill_config = data.get("skills", {})
        for old_key in ["skill_cache_dir", "skill_max_retries", "skill_force_regenerate"]:
            if old_key in data:
                new_key = old_key.replace("skill_", "")
                if new_key not in skill_config:
                    skill_config[new_key] = data.pop(old_key)
        if skill_config:
            data["skills"] = skill_config

        return cls.model_validate(data)

    def to_dict(self) -> dict:
        """Convert to dictionary (backward compatibility).

        Returns:
            Configuration dict
        """
        return self.model_dump_legacy()


# Backwards compatibility aliases
# These allow old code to continue working while migrating to new config


def load_config(path: str | Path | None = None) -> AutoLabConfig:
    """Load configuration from file or create default.

    Searches for config in the following order:
    1. Provided path
    2. Environment variable AUTOLAB_CONFIG
    3. ./autolab_config.yaml
    4. ~/.qulab/config.yaml
    5. Default configuration

    Args:
        path: Optional explicit config file path

    Returns:
        AutoLabConfig instance
    """
    if path is not None:
        return AutoLabConfig.from_file(path)

    # Check environment variable
    env_path = os.environ.get("AUTOLAB_CONFIG")
    if env_path:
        return AutoLabConfig.from_file(env_path)

    # Check default paths
    default_paths = [
        Path("autolab_config.yaml"),
        Path.home() / ".qulab" / "config.yaml",
    ]

    for p in default_paths:
        if p.exists():
            return AutoLabConfig.from_file(p)

    # Return default configuration
    return AutoLabConfig()


# Keep backwards compatibility with old dataclass-based code
# by providing a wrapper that mimics the old interface


class LegacyConfigWrapper:
    """Wrapper to provide backwards compatibility with old config interface."""

    def __init__(self, config: AutoLabConfig):
        self._config = config

    def __getattr__(self, name: str) -> Any:
        """Map old attribute names to new structure."""
        # Map old names to new names
        mappings = {
            "skills_paths": lambda: self._config.skills.paths,
            "skill_cache_dir": lambda: self._config.skills.cache_dir,
            "skill_max_retries": lambda: self._config.skills.max_retries,
            "skill_force_regenerate": lambda: self._config.skills.force_regenerate,
        }

        if name in mappings:
            return mappings[name]()

        # Try to get from new config directly
        if hasattr(self._config, name):
            return getattr(self._config, name)

        # Try to get from llm config
        if self._config.llm and hasattr(self._config.llm, name):
            return getattr(self._config.llm, name)

        raise AttributeError(f"'{self.__class__.__name__}' has no attribute '{name}'")

    def to_dict(self) -> dict[str, Any]:
        """Backwards compatible to_dict method."""
        return self._config.model_dump_legacy()

    def save(self, path: str | Path) -> None:
        """Backwards compatible save method."""
        self._config.save(path)


# Export both new and old interfaces
__all__ = [
    "AutoLabConfig",
    "LLMConfig",
    "SkillConfig",
    "ExecutorConfig",
    "MemoryConfig",
    "WorldModelConfig",
    "BusConfig",
    "load_config",
    "LegacyConfigWrapper",
]
