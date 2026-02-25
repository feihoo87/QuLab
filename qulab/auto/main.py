"""Main AutoLab class for automated experiment execution."""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator

from qulab.storage import Storage

from .agent.loop import AgentConfig, AgentEvent, AgentLoop
from .agent.memory import SessionMemory
from .config import AutoLabConfig, LLMConfig

if TYPE_CHECKING:
    from ..skills.loader import SkillLoader


class AutoLab:
    """Automated experiment framework main class."""

    def __init__(
        self,
        storage: Storage,
        llm_config: dict | LLMConfig | None = None,
        skills_path: Path | str | list[Path | str] | None = None,
        config: AutoLabConfig | None = None,
    ):
        """Initialize AutoLab.

        Args:
            storage: Storage instance for data persistence
            llm_config: LLM configuration (dict or LLMConfig)
            skills_path: Path(s) to search for skills
            config: Full AutoLab configuration
        """
        self.storage = storage

        # Handle configuration
        if config:
            self.config = config
        elif llm_config:
            if isinstance(llm_config, dict):
                self.config = AutoLabConfig(llm=LLMConfig.from_dict(llm_config))
            else:
                self.config = AutoLabConfig(llm=llm_config)
        else:
            self.config = AutoLabConfig()

        # Initialize LLM provider
        if not self.config.llm:
            raise ValueError("LLM configuration is required")

        self.llm_provider = self.config.llm.create_provider()

        # Initialize skill loader
        from .skills.loader import SkillLoader

        search_paths = []
        if skills_path:
            if isinstance(skills_path, (str, Path)):
                search_paths = [skills_path]
            else:
                search_paths = list(skills_path)
        search_paths.extend(self.config.skills_paths)

        self.skill_loader = SkillLoader(search_paths if search_paths else None)

        # Initialize tool registry
        from .tools.registry import ToolRegistry

        self.tools = ToolRegistry(
            storage=storage,
            skill_loader=self.skill_loader,
            llm_config=self.config.llm,
        )

        # Initialize session memory
        storage_path = (
            storage.base_path
            if hasattr(storage, "base_path")
            else Path("./autolab_data")
        )
        self.memory = SessionMemory(storage_path)

        # Initialize agent
        agent_config = AgentConfig(
            max_iterations=self.config.max_iterations,
            temperature=self.config.llm.temperature or 0.7,
            enable_thinking=self.config.enable_thinking,
            system_prompt=self.config.custom_system_prompt,
        )

        self.agent = AgentLoop(
            llm_provider=self.llm_provider,
            tools=self.tools,
            memory=self.memory,
            config=agent_config,
        )

        self._event_queue: asyncio.Queue | None = None
        self._current_session_id: str | None = None

    async def start(
        self,
        instruction: str | None = None,
        session_id: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Start a new experiment session.

        Args:
            instruction: Initial user instruction
            session_id: Optional session ID (creates new if not provided)

        Yields:
            AgentEvent for each step
        """
        # Create or load session
        if session_id:
            if not self.memory.load_session(session_id):
                self._current_session_id = self.memory.create_session(session_id)
            else:
                self._current_session_id = session_id
        else:
            self._current_session_id = self.memory.create_session()

        # Run agent
        async for event in self.agent.run(instruction):
            yield event

            # Handle pause events
            if event.type in ("human_query", "config_request"):
                self._event_queue = asyncio.Queue()

    async def respond(self, response: str | dict) -> AsyncIterator[AgentEvent]:
        """Respond to a human query or config request.

        Args:
            response: Response to provide

        Yields:
            AgentEvent for each step
        """
        async for event in self.agent.resume(response):
            yield event

    def get_session_history(self) -> list[dict]:
        """Get current session message history.

        Returns:
            List of message dicts
        """
        return self.memory.load_messages()

    def get_full_history(self) -> list[dict]:
        """Get full session history including decisions and tool executions.

        Returns:
            List of all records
        """
        return self.memory.get_session_history()

    def list_sessions(self) -> list[dict]:
        """List all available sessions.

        Returns:
            List of session info dicts
        """
        return self.memory.list_sessions()

    def list_skills(self, skill_type: str | None = None) -> list[str]:
        """List available skills.

        Args:
            skill_type: Filter by type ("measurement" or "analysis")

        Returns:
            List of skill names
        """
        return self.skill_loader.list_skills(skill_type)

    def get_skill_info(self, name: str) -> dict:
        """Get detailed information about a skill.

        Args:
            name: Skill name

        Returns:
            Skill information dict
        """
        skill = self.skill_loader.get(name)
        return {
            "name": skill.name,
            "type": skill.type,
            "description": skill.description,
            "capabilities": skill.capabilities,
            "inputs": skill.inputs,
            "outputs": skill.outputs,
            "metadata": skill.metadata,
        }

    @property
    def current_session_id(self) -> str | None:
        """Current session ID."""
        return self._current_session_id

    @property
    def is_paused(self) -> bool:
        """Check if waiting for human input."""
        return self.agent.is_paused
