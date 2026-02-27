"""QuLab Automatic Experiment Framework

This module provides an automated experiment framework similar to nanobot,
using LLM as the decision center for coordinating measurement and analysis tasks.

Example:
    >>> from qulab.auto import AutoLab
    >>> from qulab.storage import LocalStorage
    >>>
    >>> # Initialize storage
    >>> storage = LocalStorage("./data")
    >>>
    >>> # Initialize AutoLab with Kimi
    >>> lab = AutoLab(storage, llm_config={
    ...     "provider": "openai",
    ...     "base_url": "https://api.moonshot.cn/v1",
    ...     "api_key": "sk-...",
    ...     "model": "kimi-k2.5"
    ... })
    >>>
    >>> # Start a session
    >>> async for event in lab.start("Calibrate qubit 1 frequency"):
    ...     print(f"[{event.type}] {event.content}")

The framework consists of:
- **Agent**: ReAct decision loop that coordinates tasks
- **LLM**: Pluggable LLM providers (Anthropic, OpenAI-compatible like Kimi)
- **Skills**: YAML + Markdown files describing experiments and analyses
- **Tools**: Query, measurement, analysis, config update, and human query
- **Storage**: Persistent storage via qulab.storage
"""

from .config import (
    AutoLabConfig,
    BusConfig,
    ExecutorConfig,
    LLMConfig,
    MemoryConfig,
    SkillConfig,
    WorldModelConfig,
)
from .exceptions import (
    AutoLabError,
    ConfigError,
    LLMError,
    SessionError,
    SkillError,
    SkillNotFoundError,
    ToolError,
    ToolNotFoundError,
)
from .main import AutoLab

__all__ = [
    # Main class
    "AutoLab",
    # Configuration
    "AutoLabConfig",
    "LLMConfig",
    "SkillConfig",
    "ExecutorConfig",
    "MemoryConfig",
    "WorldModelConfig",
    "BusConfig",
    # Exceptions
    "AutoLabError",
    "SkillError",
    "SkillNotFoundError",
    "ToolError",
    "ToolNotFoundError",
    "LLMError",
    "ConfigError",
    "SessionError",
]


def __getattr__(name):
    """Lazy import for agent components."""
    if name == "AgentLoop":
        from .agent.loop import AgentLoop
        return AgentLoop
    if name == "AgentConfig":
        from .agent.loop import AgentConfig
        return AgentConfig
    if name == "AgentEvent":
        from .agent.loop import AgentEvent
        return AgentEvent
    if name == "PlannerAgent":
        from .agent.planner import PlannerAgent
        return PlannerAgent
    if name == "ExecutorAgent":
        from .agent.executor import ExecutorAgent
        return ExecutorAgent
    if name == "AnalysisAgent":
        from .agent.analyzer import AnalysisAgent
        return AnalysisAgent
    if name == "Skill":
        from .skills.base import Skill
        return Skill
    if name == "SkillLoader":
        from .skills.loader import SkillLoader
        return SkillLoader
    if name == "MessageBus":
        from .bus import MessageBus
        return MessageBus
    if name == "WorldModel":
        from .world_model import WorldModel
        return WorldModel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
