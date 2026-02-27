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

    type: str  # "thinking", "tool_call", "tool_result", "complete", "error"
                # "human_query", "config_request"
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

            # Process thinking if present (skip for models that don't support it well)
            if response.content and self.config.enable_thinking:
                # Skip thinking events if content looks like tool call reasoning
                # Some models (like Kimi k2.5) have issues with thinking + tool calls
                if not (response.tool_calls and "kimi" in self.llm.name.lower()):
                    yield AgentEvent(
                        type="thinking",
                        content=response.content,
                    )

            # Add assistant message with tool calls
            assistant_content = response.content or ""

            # For Kimi models with reasoning_content, handle it properly
            if "kimi" in self.llm.name.lower() and response.reasoning_content:
                # Kimi requires reasoning_content to be preserved in assistant messages
                assistant_content = ""  # Content is empty when there are tool calls

            assistant_message = {
                "role": "assistant",
                "content": assistant_content,
            }

            # Add reasoning_content for models that support it (e.g., Kimi)
            if response.reasoning_content:
                assistant_message["reasoning_content"] = response.reasoning_content

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

        # For Kimi models, remove thinking-related words to avoid triggering thinking mode
        # which causes API errors with tool calls
        if "kimi" in self.llm.name.lower():
            system_prompt = self._sanitize_for_kimi(system_prompt)

        context = [{"role": "system", "content": system_prompt}] + messages

        # For Kimi models, add extra instruction to avoid thinking format
        if "kimi" in self.llm.name.lower():
            context[0]["content"] += "\n\nIMPORTANT: Do NOT use <thinking> tags or any special reasoning format. Just provide plain text responses and tool calls."

        return context

    def _sanitize_for_kimi(self, text: str) -> str:
        """Remove thinking-related words that trigger Kimi's thinking mode.

        Args:
            text: Input text

        Returns:
            Sanitized text
        """
        # Replace thinking-related words with alternatives
        replacements = {
            "thinking": "analysis",
            "thinking": "analysis",
            "thinking": "analysis",
            "reasoning": "explanation",
            "reasoning": "explanation",
            "reason": "rationale",
        }

        result = text
        for old, new in replacements.items():
            result = result.replace(old, new)
            result = result.replace(old.capitalize(), new.capitalize())
            result = result.replace(old.upper(), new.upper())

        return result

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

6. **save_lesson**: Save a lesson learned from experience
   - Use after solving a problem or discovering important insights
   - Record problem, solution, and related skill

7. **query_lessons**: Query previously saved lessons
   - Use before executing a skill to check for known issues
   - Search by skill name or keyword

8. **create_guide**: Create a comprehensive guide from accumulated lessons
   - Compile multiple lessons into a skill usage guide

## Decision Guidelines

1. **Start by assessing the current state**: Query storage to see what data exists
2. **Check for lessons**: Before executing a skill, query_lessons to see if there are known issues
3. **Plan the workflow**: Determine what measurements/analyses are needed
4. **Execute skills**: Use run_measurement or run_analysis as appropriate
5. **Review results**: Check if further action is needed
6. **Save lessons**: After fixing problems or discovering insights, save_lesson for future reference
7. **Ask when uncertain**: Use ask_human when not sure what to do

## Important Rules

- Always query existing data before running new measurements
- Query lessons before executing a skill to learn from past experience
- Provide clear reasoning for your decisions
- Configuration updates require human approval
- Analysis can use multiple datasets - specify their IDs
- If a measurement fails:
  1. Analyze the error and try to fix it
  2. If fixed, save_lesson to document the solution
  3. If still stuck after 2 attempts, ask_human for help
- Always save a lesson when you learn something important

## Measurement Dependencies

Quantum measurements have dependencies that must be satisfied:

1. **Resonator Spectroscopy (腔频测量)**: Usually the first measurement
   - No dependencies - can run directly
   - Output: Resonator frequency (fr)

2. **Qubit Spectroscopy (Qubit 能谱)**: Depends on resonator frequency
   - Requires: readout_frequency (from resonator_spectroscopy)
   - Output: Qubit frequency (fq)

3. **Rabi Measurement**: Depends on qubit frequency
   - Requires: qubit_frequency (from qubit_spectroscopy)
   - Output: Pi-pulse duration (pi_pulse_duration)

4. **T1 Measurement**: Depends on pi-pulse
   - Requires: pi_pulse_duration (from rabi_measurement)
   - Output: T1 time constant

5. **T2 Measurement**: Depends on pi-pulse
   - Requires: pi_pulse_duration (from rabi_measurement)
   - Output: T2 time constant

6. **T2 Echo Measurement**: Depends on pi-pulse
   - Requires: pi_pulse_duration (from rabi_measurement)
   - Output: T2_echo time constant

## Typical Workflow Example

Measuring T1 standard workflow:
```
1. Measure resonator frequency (resonator_spectroscopy)
   → Get resonator frequency

2. Analyze resonator data (lorentzian_fit)
   → Confirm resonator peak

3. Measure qubit spectroscopy (qubit_spectroscopy)
   → Use resonator frequency for readout
   → Get qubit frequency

4. Perform Rabi measurement (rabi_measurement)
   → Use qubit frequency
   → Get pi_pulse_duration

5. Perform T1 measurement (t1_measurement)
   → Use pi_pulse_duration from Rabi
   → Output: T1 decay data

6. Analyze T1 data (decay_fit)
   → Get T1 time constant
   → Report final result
```

## Execution Strategy

When given a goal (e.g., "measure T1"):
1. First query_storage to check what data already exists
2. Determine which measurements are needed based on dependencies
3. Execute missing measurements in order
4. Use analysis skills to extract final results
5. Report the final answer to the user

## Response Format

Provide clear reasoning for your decisions, then make tool calls to take action.

IMPORTANT: When making tool calls, do NOT use <thinking> tags or any special formatting. Simply provide your reasoning in plain text, then make the tool calls.
"""

    @property
    def is_paused(self) -> bool:
        """Check if loop is paused waiting for human input."""
        return self._paused
