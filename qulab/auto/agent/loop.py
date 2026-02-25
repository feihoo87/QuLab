"""Agent decision loop implementing ReAct pattern."""

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, AsyncIterator

if TYPE_CHECKING:
    from ..llm.base import LLMProvider
    from ..tools.registry import ToolRegistry
    from .memory import SessionMemory


@dataclass
class AgentConfig:
    """Configuration for agent loop."""

    max_iterations: int = 40
    temperature: float = 0.7
    enable_thinking: bool = True
    system_prompt: str | None = None


@dataclass
class AgentEvent:
    """Event emitted by agent loop."""

    type: str  # "thinking", "tool_call", "tool_result", "complete", "error", "human_query", "config_request"
    content: str | None = None
    tool_name: str | None = None
    tool_args: dict | None = None
    result: dict | None = None
    question: str | None = None
    options: list[str] | None = None
    updates: dict | None = None
    reason: str | None = None
    metadata: dict = field(default_factory=dict)


class AgentLoop:
    """ReAct decision loop for automated experiment execution."""

    def __init__(
        self,
        llm_provider: "LLMProvider",
        tools: "ToolRegistry",
        memory: "SessionMemory",
        config: AgentConfig | None = None,
    ):
        """Initialize agent loop.

        Args:
            llm_provider: LLM provider for decision making
            tools: Tool registry with available tools
            memory: Session memory for persistence
            config: Agent configuration
        """
        self.llm = llm_provider
        self.tools = tools
        self.memory = memory
        self.config = config or AgentConfig()
        self._paused = False
        self._pending_response = None

    async def run(
        self,
        initial_message: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Run the decision loop.

        Args:
            initial_message: Initial user message

        Yields:
            AgentEvent for each step
        """
        # Load existing messages from memory
        messages = self.memory.load_messages()

        # Add initial message if provided
        if initial_message:
            messages.append({"role": "user", "content": initial_message})
            self.memory.append_message("user", initial_message)

        iteration = 0
        while iteration < self.config.max_iterations:
            iteration += 1

            # Build context with system prompt
            context = self._build_context(messages)

            # Call LLM
            try:
                response = await self.llm.chat(
                    messages=context,
                    tools=self.tools.get_definitions(),
                )
            except Exception as e:
                yield AgentEvent(
                    type="error",
                    content=f"LLM call failed: {str(e)}",
                )
                return

            # Check if response has tool calls
            if not response.tool_calls:
                # Final response - no more actions needed
                self.memory.append_message("assistant", response.content or "")
                yield AgentEvent(
                    type="complete",
                    content=response.content,
                )
                return

            # Process thinking if present
            if response.content and self.config.enable_thinking:
                yield AgentEvent(
                    type="thinking",
                    content=response.content,
                )

            # Add assistant message with tool calls
            assistant_message = {
                "role": "assistant",
                "content": response.content or "",
            }

            # Add tool_calls in OpenAI format
            if response.tool_calls:
                assistant_message["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ]

            messages.append(assistant_message)
            self.memory.append_message(
                "assistant",
                response.content or "",
                tool_calls=[
                    {"name": tc.name, "arguments": tc.arguments}
                    for tc in response.tool_calls
                ],
            )

            # Execute tool calls
            for tool_call in response.tool_calls:
                yield AgentEvent(
                    type="tool_call",
                    tool_name=tool_call.name,
                    tool_args=tool_call.arguments,
                    content=f"Executing {tool_call.name}({json.dumps(tool_call.arguments)})",
                )

                try:
                    result = await self.tools.execute(
                        tool_call.name,
                        tool_call.arguments,
                    )

                    # Handle special results (human interruption, config request)
                    from ..tools.config import ConfigUpdateRequest
                    from ..tools.human import HumanInterruption

                    if isinstance(result, ConfigUpdateRequest) or (
                        hasattr(result, "error")
                        and result.error
                        and "ConfigUpdateRequest" in result.error
                    ):
                        # Extract the actual exception info
                        try:
                            result = await self.tools.execute(
                                tool_call.name,
                                tool_call.arguments,
                            )
                        except ConfigUpdateRequest as e:
                            yield AgentEvent(
                                type="config_request",
                                updates=e.updates,
                                reason=e.reason,
                            )
                            self._paused = True
                            return

                    if isinstance(result, HumanInterruption) or (
                        hasattr(result, "error")
                        and result.error
                        and "HumanInterruption" in result.error
                    ):
                        try:
                            result = await self.tools.execute(
                                tool_call.name,
                                tool_call.arguments,
                            )
                        except HumanInterruption as e:
                            yield AgentEvent(
                                type="human_query",
                                question=e.question,
                                options=e.options,
                                content=e.question,
                            )
                            self._paused = True
                            return

                    # Normal result
                    tool_result_content = json.dumps(result.to_dict())

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result_content,
                    })
                    self.memory.append_message(
                        "tool",
                        tool_result_content,
                        tool_call_id=tool_call.id,
                    )

                    yield AgentEvent(
                        type="tool_result",
                        result=result.to_dict(),
                        content=f"Result: {result.to_dict()}",
                    )

                except ConfigUpdateRequest as e:
                    yield AgentEvent(
                        type="config_request",
                        updates=e.updates,
                        reason=e.reason,
                    )
                    self._paused = True
                    return

                except HumanInterruption as e:
                    yield AgentEvent(
                        type="human_query",
                        question=e.question,
                        options=e.options,
                        content=e.question,
                    )
                    self._paused = True
                    return

                except Exception as e:
                    error_msg = f"Error executing {tool_call.name}: {str(e)}"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"error": error_msg}),
                    })
                    self.memory.append_message(
                        "tool",
                        json.dumps({"error": error_msg}),
                        tool_call_id=tool_call.id,
                    )
                    yield AgentEvent(
                        type="error",
                        content=error_msg,
                    )

        # Max iterations reached
        yield AgentEvent(
            type="error",
            content=f"Reached maximum iterations ({self.config.max_iterations})",
        )

    async def resume(self, response: str | dict) -> AsyncIterator[AgentEvent]:
        """Resume execution after human response.

        Args:
            response: Human response

        Yields:
            AgentEvent for each step
        """
        # Add human response as a user message
        if isinstance(response, dict):
            content = json.dumps(response)
        else:
            content = response

        # Create a new run with the response
        messages = self.memory.load_messages()
        messages.append({"role": "user", "content": content})
        self.memory.append_message("user", content)

        self._paused = False

        async for event in self.run():
            yield event

    def _build_context(self, messages: list[dict]) -> list[dict]:
        """Build context with system prompt.

        Args:
            messages: Current messages

        Returns:
            Full context with system prompt
        """
        system_prompt = self._build_system_prompt()
        return [{"role": "system", "content": system_prompt}] + messages

    def _build_system_prompt(self) -> str:
        """Build system prompt with skills and instructions.

        Returns:
            System prompt string
        """
        # Use custom system prompt if provided
        if self.config.system_prompt:
            return self.config.system_prompt

        # Build default system prompt
        skills_summary = self.tools.skill_loader.build_summary()

        return f"""You are an automated experiment framework AI agent. Your role is to coordinate measurement and analysis tasks for quantum experiments.

## Available Skills

{skills_summary}

## Available Tools

You have access to the following tools:

1. **query_storage**: Query existing datasets and documents
   - Use to check what data already exists
   - Filter by name, tags, state, or time

2. **run_measurement**: Execute a measurement skill
   - Creates a new Dataset with results
   - Provide skill name and parameters

3. **run_analysis**: Execute an analysis skill
   - Creates a new Document with results
   - Provide dataset IDs to analyze

4. **update_config**: Request configuration updates
   - Use when parameters need adjustment
   - Provide updates and reason

5. **ask_human**: Ask for human input or confirmation
   - Use when uncertain or approval needed
   - Provide clear question and optional options

## Decision Guidelines

1. **Start by assessing the current state**: Query storage to see what data exists
2. **Plan the workflow**: Determine what measurements/analyses are needed
3. **Execute skills**: Use run_measurement or run_analysis as appropriate
4. **Review results**: Check if further action is needed
5. **Ask when uncertain**: Use ask_human when not sure what to do

## Important Rules

- Always query existing data before running new measurements
- Provide clear reasoning for your decisions
- Configuration updates require human approval
- Analysis can use multiple datasets - specify their IDs
- If a measurement fails, try adjusting parameters or ask the human

## Response Format

Use the <think> tags to show your reasoning process, then make tool calls to take action.

Example:
<thinking>
I need to check if there's existing qubit spectroscopy data before running a new measurement.
</thinking>
[Tool call to query_storage]
"""

    @property
    def is_paused(self) -> bool:
        """Check if loop is paused waiting for human input."""
        return self._paused
