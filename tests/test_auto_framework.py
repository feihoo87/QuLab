"""Tests for the auto experiment framework.

This test file verifies the core functionality of the auto experiment framework
without requiring actual LLM API calls.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from qulab.auto import AutoLab, AutoLabConfig, LLMConfig
from qulab.auto.agent.loop import AgentConfig, AgentLoop
from qulab.auto.agent.memory import SessionMemory
from qulab.auto.skills.base import Skill
from qulab.auto.skills.loader import SkillLoader
from qulab.auto.tools.base import BaseTool, ToolResult
from qulab.auto.tools.registry import ToolRegistry
from qulab.storage import LocalStorage


class MockLLMProvider:
    """Mock LLM provider for testing."""

    def __init__(self, responses=None):
        self.responses = responses or []
        self.call_count = 0

    @property
    def name(self):
        return "mock:test"

    async def chat(self, messages, tools=None, tool_choice="auto"):
        """Return predefined responses."""
        from qulab.auto.llm.base import LLMResponse, ToolCall

        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
            self.call_count += 1
            return response

        # Default: return completion
        return LLMResponse(
            content="Task completed",
            tool_calls=[],
            model="mock",
        )


class MockTool(BaseTool):
    """Mock tool for testing."""

    name = "mock_tool"
    description = "A mock tool for testing"
    parameters = {
        "param1": {
            "type": "string",
            "description": "Test parameter",
            "required": True,
        }
    }

    async def execute(self, param1=None, **kwargs):
        return ToolResult(data={"received": param1})


@pytest.fixture
def temp_storage():
    """Create a temporary storage instance."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(tmpdir)
        yield storage


@pytest.fixture
def sample_skill_file(tmp_path):
    """Create a sample skill file."""
    skill_dir = tmp_path / "test_skill"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("""---
name: test_measurement
type: measurement
description: A test measurement skill
capabilities:
  test:
    - test capability
inputs:
  - name: value
    type: number
    description: Input value
    default: 1.0
outputs:
  - name: result
    type: number
    description: Result value
metadata:
  tags: [test]
---

```python
def run(value=1.0, ctx=None):
    return {
        'dataset': {'x': [1, 2, 3], 'y': [value, value*2, value*3]},
        'result': value * 2
    }
```
""")
    return skill_dir.parent


class TestSkillLoader:
    """Tests for SkillLoader."""

    def test_load_skill_from_file(self, sample_skill_file):
        """Test loading a skill from file."""
        loader = SkillLoader([sample_skill_file])
        skills = loader.load_all()

        assert "test_measurement" in skills
        skill = skills["test_measurement"]
        assert skill.type == "measurement"
        assert "test" in skill.metadata.get("tags", [])

    def test_skill_to_prompt(self, sample_skill_file):
        """Test skill to_prompt method."""
        loader = SkillLoader([sample_skill_file])
        skills = loader.load_all()
        skill = skills["test_measurement"]

        prompt = skill.to_prompt()
        assert "test_measurement" in prompt
        assert "measurement" in prompt
        assert "value" in prompt

    def test_validate_inputs(self, sample_skill_file):
        """Test input validation."""
        loader = SkillLoader([sample_skill_file])
        skills = loader.load_all()
        skill = skills["test_measurement"]

        # Should pass with valid input
        errors = skill.validate_inputs({"value": 5.0})
        assert len(errors) == 0

        # Should pass with default
        errors = skill.validate_inputs({})
        assert len(errors) == 0


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_register_tool(self, temp_storage):
        """Test tool registration."""
        loader = SkillLoader()
        registry = ToolRegistry(temp_storage, loader)

        mock_tool = MockTool()
        registry.register(mock_tool)

        assert "mock_tool" in registry.list_tools()
        assert registry.get("mock_tool") == mock_tool

    def test_tool_definitions(self, temp_storage):
        """Test getting tool definitions for LLM."""
        loader = SkillLoader()
        registry = ToolRegistry(temp_storage, loader)

        definitions = registry.get_definitions()
        assert isinstance(definitions, list)

        # Should have builtin tools
        tool_names = [d["function"]["name"] for d in definitions]
        assert "query_storage" in tool_names

    @pytest.mark.asyncio
    async def test_execute_tool(self, temp_storage):
        """Test tool execution."""
        loader = SkillLoader()
        registry = ToolRegistry(temp_storage, loader)

        registry.register(MockTool())

        result = await registry.execute("mock_tool", {"param1": "hello"})
        assert result.success
        assert result.data["received"] == "hello"

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, temp_storage):
        """Test executing unknown tool returns error."""
        loader = SkillLoader()
        registry = ToolRegistry(temp_storage, loader)

        result = await registry.execute("unknown_tool", {})
        assert not result.success
        assert "Unknown tool" in result.error


class TestToolResult:
    """Tests for ToolResult."""

    def test_success_property(self):
        """Test success property."""
        result = ToolResult(data={"x": 1})
        assert result.success

        result = ToolResult(error="failed")
        assert not result.success

    def test_to_dict(self):
        """Test to_dict method."""
        result = ToolResult(data={"x": 1}, metadata={"y": 2})
        d = result.to_dict()
        assert d["success"] is True
        assert d["data"]["x"] == 1


class TestSessionMemory:
    """Tests for SessionMemory."""

    def test_create_session(self, tmp_path):
        """Test session creation."""
        memory = SessionMemory(tmp_path)
        session_id = memory.create_session("test_session")

        assert session_id == "test_session"
        assert memory.current_session == "test_session"

        # Check session file exists
        session_file = tmp_path / "sessions" / "test_session.jsonl"
        assert session_file.exists()

    def test_append_and_load_messages(self, tmp_path):
        """Test appending and loading messages."""
        memory = SessionMemory(tmp_path)
        memory.create_session()

        memory.append_message("user", "Hello")
        memory.append_message("assistant", "Hi there")

        messages = memory.load_messages()
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"

    def test_list_sessions(self, tmp_path):
        """Test listing sessions."""
        memory = SessionMemory(tmp_path)
        memory.create_session("session1")
        memory.create_session("session2")

        sessions = memory.list_sessions()
        assert len(sessions) == 2
        session_ids = [s["session_id"] for s in sessions]
        assert "session1" in session_ids
        assert "session2" in session_ids


class TestAutoLab:
    """Tests for AutoLab main class."""

    def test_initialization(self, temp_storage):
        """Test AutoLab initialization."""
        config = AutoLabConfig(
            llm=LLMConfig(
                provider="openai",
                model="test-model",
                base_url="http://test",
                api_key="test-key",
            )
        )

        lab = AutoLab(temp_storage, config=config)
        assert lab.storage == temp_storage
        assert lab.config == config

    def test_list_skills(self, temp_storage, sample_skill_file):
        """Test listing skills."""
        config = AutoLabConfig(
            llm=LLMConfig(
                provider="openai",
                model="test-model",
                base_url="http://test",
                api_key="test-key",
            )
        )

        lab = AutoLab(temp_storage, config=config, skills_path=sample_skill_file)
        skills = lab.list_skills()

        assert "test_measurement" in skills

    def test_get_skill_info(self, temp_storage, sample_skill_file):
        """Test getting skill info."""
        config = AutoLabConfig(
            llm=LLMConfig(
                provider="openai",
                model="test-model",
                base_url="http://test",
                api_key="test-key",
            )
        )

        lab = AutoLab(temp_storage, config=config, skills_path=sample_skill_file)
        info = lab.get_skill_info("test_measurement")

        assert info["name"] == "test_measurement"
        assert info["type"] == "measurement"


class TestAgentLoop:
    """Tests for AgentLoop."""

    @pytest.mark.asyncio
    async def test_run_with_completion(self, temp_storage):
        """Test agent loop running to completion."""
        from qulab.auto.llm.base import LLMResponse

        # Create mock LLM that completes immediately
        mock_llm = MockLLMProvider([
            LLMResponse(content="Done", tool_calls=[], model="mock"),
        ])

        loader = SkillLoader()
        registry = ToolRegistry(temp_storage, loader)
        memory = SessionMemory(temp_storage.base_path)
        memory.create_session()

        config = AgentConfig(max_iterations=10)
        agent = AgentLoop(mock_llm, registry, memory, config)

        events = []
        async for event in agent.run("Test instruction"):
            events.append(event)

        # Should have at least one event
        assert len(events) > 0
        assert events[-1].type == "complete"

    @pytest.mark.asyncio
    async def test_run_with_tool_call(self, temp_storage):
        """Test agent loop with tool execution."""
        from qulab.auto.llm.base import LLMResponse, ToolCall

        # Create mock LLM that calls a tool then completes
        mock_llm = MockLLMProvider([
            LLMResponse(
                content="Using tool",
                tool_calls=[ToolCall(id="1", name="mock_tool", arguments={"param1": "test"})],
                model="mock",
            ),
            LLMResponse(content="Done", tool_calls=[], model="mock"),
        ])

        loader = SkillLoader()
        registry = ToolRegistry(temp_storage, loader)
        registry.register(MockTool())

        memory = SessionMemory(temp_storage.base_path)
        memory.create_session()

        config = AgentConfig(max_iterations=10)
        agent = AgentLoop(mock_llm, registry, memory, config)

        events = []
        async for event in agent.run("Test"):
            events.append(event)

        event_types = [e.type for e in events]
        assert "tool_call" in event_types
        assert "tool_result" in event_types


class TestLLMConfig:
    """Tests for LLMConfig."""

    def test_from_dict(self):
        """Test creating config from dict."""
        data = {
            "provider": "openai",
            "model": "gpt-4",
            "base_url": "https://api.example.com",
            "api_key": "secret",
            "temperature": 0.5,
            "max_tokens": 2048,
        }

        config = LLMConfig.from_dict(data)
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.temperature == 0.5

    def test_to_dict(self):
        """Test converting config to dict."""
        config = LLMConfig(
            provider="anthropic",
            model="claude-3",
            api_key="secret",
        )

        data = config.to_dict()
        assert data["provider"] == "anthropic"
        assert data["model"] == "claude-3"


class TestIntegration:
    """Integration tests."""

    @pytest.mark.asyncio
    async def test_full_workflow_mock(self, temp_storage, sample_skill_file):
        """Test full workflow with mocked components."""
        from qulab.auto.llm.base import LLMResponse, ToolCall

        # Setup
        config = AutoLabConfig(
            llm=LLMConfig(
                provider="openai",
                model="test",
                base_url="http://test",
                api_key="test",
            )
        )

        lab = AutoLab(
            temp_storage,
            config=config,
            skills_path=sample_skill_file,
        )

        # Replace LLM with mock
        mock_responses = [
            # First: query storage
            LLMResponse(
                content="Checking storage",
                tool_calls=[
                    ToolCall(id="1", name="query_storage", arguments={"type": "dataset"}),
                ],
                model="mock",
            ),
            # Second: complete
            LLMResponse(content="Workflow complete", tool_calls=[], model="mock"),
        ]
        lab.llm_provider = MockLLMProvider(mock_responses)

        # Re-create agent with mock LLM
        lab.agent = AgentLoop(
            llm_provider=lab.llm_provider,
            tools=lab.tools,
            memory=lab.memory,
            config=AgentConfig(max_iterations=10),
        )

        # Run
        events = []
        async for event in lab.start("Test workflow"):
            events.append(event)

        # Verify
        assert len(events) > 0
        assert any(e.type == "tool_call" for e in events)
        assert events[-1].type == "complete"


def test_skill_loader_builtin_skills():
    """Test that builtin skills are loaded."""
    loader = SkillLoader()
    skills = loader.load_all()

    # Should have builtin skills
    assert len(skills) >= 1
    assert "basic_measurement" in skills


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
