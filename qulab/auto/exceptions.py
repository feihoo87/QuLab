"""Exceptions for auto experiment framework."""


class AutoLabError(Exception):
    """Base exception for auto lab."""
    pass


class SkillError(AutoLabError):
    """Error loading or executing a skill."""
    pass


class SkillNotFoundError(SkillError):
    """Skill not found."""
    pass


class ToolError(AutoLabError):
    """Error executing a tool."""
    pass


class ToolNotFoundError(ToolError):
    """Tool not found."""
    pass


class LLMError(AutoLabError):
    """Error from LLM provider."""
    pass


class ConfigError(AutoLabError):
    """Configuration error."""
    pass


class SessionError(AutoLabError):
    """Session management error."""
    pass
