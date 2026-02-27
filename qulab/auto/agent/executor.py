"""Executor Agent for experiment skill execution.

The Executor Agent is responsible for:
- Parsing experiment Skill Markdown documents
- Generating Python code from skill descriptions
- Executing generated code to control hardware
- Debugging and retrying on failures
- Saving raw data to Dataset
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from ..bus import Event, EventType, MessageBus
from ..skills import Skill


@dataclass
class ExecutionContext:
    """Context for skill execution.

    Attributes:
        session_id: Session identifier
        execution_id: Unique execution identifier
        parameters: Execution parameters
        world_model: World model access
        config: Execution configuration
    """

    session_id: str
    execution_id: str
    parameters: dict[str, Any] = field(default_factory=dict)
    world_model: Any = None
    config: Any = None


@dataclass
class ExecutionResult:
    """Result of skill execution.

    Attributes:
        status: Execution status (success/failed)
        dataset_id: ID of created dataset (if successful)
        error: Error message (if failed)
        reason: Failure reason code
        execution_time: Time taken to execute
        attempts: Number of execution attempts
        code: The executed code
    """

    status: str  # "success" | "failed"
    dataset_id: str | None = None
    error: str | None = None
    reason: str | None = None
    execution_time: float = 0.0
    attempts: int = 0
    code: str | None = None


class ExecutorAgent:
    """Execution layer Agent for experiment skills.

    The Executor Agent parses experiment Skill Markdown documents,
    generates Python code, and executes it to control hardware.
    It handles the complete execution-debugging loop.

    Example:
        ```python
        executor = ExecutorAgent(
            llm=llm_provider,
            code_generator=code_generator,
            code_executor=code_executor,
            storage=storage,
            bus=message_bus
        )

        # Execute a skill
        result = await executor.execute(
            skill=skill,
            parameters={"qubit_id": "Q1", "frequency": 5.2e9},
            context=execution_context
        )

        if result.status == "success":
            print(f"Data saved to dataset: {result.dataset_id}")
        ```
    """

    def __init__(
        self,
        llm,
        code_generator,
        code_executor,
        storage,
        bus: MessageBus | None = None,
        max_retries: int = 3,
    ):
        """Initialize the Executor Agent.

        Args:
            llm: LLM provider for code fixing
            code_generator: Code generator for skill code
            code_executor: Code executor for running code
            storage: Storage backend for datasets
            bus: Optional MessageBus for events
            max_retries: Maximum retry attempts
        """
        self.llm = llm
        self.generator = code_generator
        self.executor = code_executor
        self.storage = storage
        self.bus = bus
        self.max_retries = max_retries

        logger.info("Executor Agent initialized")

    async def execute(
        self,
        skill: Skill,
        parameters: dict[str, Any],
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Execute an experiment skill.

        This method:
        1. Parses the skill strategy
        2. Checks prerequisites
        3. Generates or retrieves code
        4. Executes with retry loop
        5. Saves results to dataset

        Args:
            skill: The skill to execute
            parameters: Execution parameters
            context: Execution context

        Returns:
            ExecutionResult
        """
        import uuid

        execution_id = str(uuid.uuid4())
        start_time = time.time()

        logger.info(f"Executing skill: {skill.name} (execution_id: {execution_id})")

        # Publish skill start event
        if self.bus:
            await self.bus.publish(
                Event(
                    type=EventType.SKILL_START,
                    payload={
                        "execution_id": execution_id,
                        "skill_id": skill.id,
                        "skill_name": skill.name,
                        "parameters": parameters,
                    },
                    session_id=context.session_id,
                    source="executor_agent",
                )
            )

        try:
            # 1. Parse skill strategy
            strategy = self._parse_strategy(skill)

            # 2. Check prerequisites
            prereq_result = self._check_prerequisites(strategy, context)
            if not prereq_result:
                return ExecutionResult(
                    status="failed",
                    reason="prerequisites_not_met",
                    execution_time=time.time() - start_time,
                )

            # 3. Generate or get cached code
            code = await self._get_code(skill, parameters, context)

            # 4. Execute with retry loop
            result_data = None
            final_error = None

            for attempt in range(1, self.max_retries + 1):
                logger.debug(f"Execution attempt {attempt}/{self.max_retries}")

                try:
                    exec_result = await self.executor.execute(
                        code=code,
                        context=context,
                        timeout=getattr(context.config, "max_execution_time", 600.0),
                    )

                    if exec_result.success:
                        result_data = exec_result.data
                        break
                    else:
                        final_error = exec_result.error
                        logger.warning(f"Execution failed: {final_error}")

                        # Try to fix the code
                        if attempt < self.max_retries:
                            code = await self._fix_code(code, final_error, skill)

                except asyncio.TimeoutError:
                    final_error = "Execution timeout"
                    logger.error(final_error)
                    break
                except Exception as e:
                    final_error = str(e)
                    logger.exception("Execution error")
                    if attempt < self.max_retries:
                        code = await self._fix_code(code, final_error, skill)

            if result_data is None:
                # Publish skill error event
                if self.bus:
                    await self.bus.publish(
                        Event(
                            type=EventType.SKILL_ERROR,
                            payload={
                                "execution_id": execution_id,
                                "skill_id": skill.id,
                                "error": final_error,
                                "attempts": attempt,
                            },
                            session_id=context.session_id,
                            source="executor_agent",
                        )
                    )

                return ExecutionResult(
                    status="failed",
                    reason="max_retries_exceeded",
                    error=final_error,
                    execution_time=time.time() - start_time,
                    attempts=attempt,
                    code=code,
                )

            # 5. Save results to dataset
            dataset_id = await self._save_results(
                result_data, skill, parameters, execution_id, code
            )

            execution_time = time.time() - start_time

            # Publish skill complete event
            if self.bus:
                await self.bus.publish(
                    Event(
                        type=EventType.SKILL_COMPLETE,
                        payload={
                            "execution_id": execution_id,
                            "skill_id": skill.id,
                            "dataset_id": dataset_id,
                            "execution_time": execution_time,
                        },
                        session_id=context.session_id,
                        source="executor_agent",
                    )
                )

            logger.info(f"Skill execution completed: {skill.name}")

            return ExecutionResult(
                status="success",
                dataset_id=dataset_id,
                execution_time=execution_time,
                attempts=attempt,
                code=code,
            )

        except Exception as e:
            logger.exception("Unexpected error during skill execution")

            # Publish skill error event
            if self.bus:
                await self.bus.publish(
                    Event(
                        type=EventType.SKILL_ERROR,
                        payload={
                            "execution_id": execution_id,
                            "skill_id": skill.id,
                            "error": str(e),
                        },
                        session_id=context.session_id,
                        source="executor_agent",
                    )
                )

            return ExecutionResult(
                status="failed",
                reason="unexpected_error",
                error=str(e),
                execution_time=time.time() - start_time,
            )

    def _parse_strategy(self, skill: Skill) -> dict[str, Any]:
        """Parse the strategy section from skill.

        Args:
            skill: The skill to parse

        Returns:
            Strategy dictionary
        """
        strategy = {
            "description": skill.description,
            "prerequisites": [],
            "steps": [],
        }

        # Extract from metadata if available
        if hasattr(skill, "metadata") and skill.metadata:
            strategy["prerequisites"] = skill.metadata.get("requires", [])

        return strategy

    def _check_prerequisites(
        self, strategy: dict[str, Any], context: ExecutionContext
    ) -> bool:
        """Check if prerequisites are met.

        Args:
            strategy: Parsed strategy
            context: Execution context

        Returns:
            True if prerequisites are met
        """
        prerequisites = strategy.get("prerequisites", [])

        if not prerequisites:
            return True

        # Check against world model
        if context.world_model:
            for prereq in prerequisites:
                if isinstance(prereq, str):
                    # Simple path check
                    param = context.world_model.get_parameter(prereq)
                    if param is None or param.is_expired():
                        logger.warning(f"Prerequisite not met: {prereq}")
                        return False
                elif isinstance(prereq, dict):
                    # Complex prerequisite check
                    for key, value in prereq.items():
                        param = context.world_model.get_parameter(key)
                        if param is None:
                            logger.warning(f"Prerequisite not met: {key}")
                            return False

        return True

    async def _get_code(
        self,
        skill: Skill,
        parameters: dict[str, Any],
        context: ExecutionContext,
    ) -> str:
        """Get code for the skill (from cache or generate).

        Args:
            skill: The skill
            parameters: Execution parameters
            context: Execution context

        Returns:
            Python code string
        """
        # Check if skill has direct code
        if hasattr(skill, "generation_mode") and skill.generation_mode == "direct":
            # Use embedded code
            return self._extract_code_from_skill(skill)

        # Check cache
        cache_key = self._generate_cache_key(skill, parameters)
        # TODO: Check code cache

        # Generate code
        code = await self.generator.generate(skill, parameters, context)

        # TODO: Cache the generated code

        return code

    def _extract_code_from_skill(self, skill: Skill) -> str:
        """Extract code from a direct mode skill.

        Args:
            skill: The skill

        Returns:
            Python code
        """
        import re

        # Extract code blocks from guide content
        if not hasattr(skill, "guide") or not skill.guide:
            return ""

        code_blocks = re.findall(
            r"```python\n(.*?)\n```", skill.guide, re.DOTALL
        )

        if code_blocks:
            return "\n\n".join(code_blocks)

        return skill.guide

    async def _fix_code(
        self,
        code: str,
        error: str,
        skill: Skill,
    ) -> str:
        """Attempt to fix code based on error.

        Args:
            code: Original code
            error: Error message
            skill: The skill being executed

        Returns:
            Fixed code
        """
        logger.info(f"Attempting to fix code for error: {error[:100]}...")

        prompt = f"""The following Python code generated for skill '{skill.name}' failed with an error.

Please fix the code:

## Error
{error}

## Original Code
```python
{code}
```

## Skill Description
{skill.description}

Please provide only the fixed Python code, no explanations."""

        try:
            response = await self.llm.chat(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Python programmer who fixes code errors.",
                    },
                    {"role": "user", "content": prompt},
                ]
            )

            fixed_code = response.content

            # Extract code if wrapped in markdown
            import re

            code_match = re.search(
                r"```python\n(.*?)\n```", fixed_code, re.DOTALL
            )
            if code_match:
                fixed_code = code_match.group(1)

            return fixed_code

        except Exception as e:
            logger.error(f"Code fixing failed: {e}")
            return code  # Return original code on failure

    async def _save_results(
        self,
        result_data: Any,
        skill: Skill,
        parameters: dict[str, Any],
        execution_id: str,
        code: str,
    ) -> str | None:
        """Save execution results to a dataset.

        Args:
            result_data: Execution result data
            skill: Executed skill
            parameters: Execution parameters
            execution_id: Execution identifier
            code: Executed code

        Returns:
            Dataset ID or None
        """
        if not self.storage:
            logger.warning("No storage configured, results not saved")
            return None

        try:
            # Create dataset
            dataset = self.storage.create_dataset(
                name=f"{skill.name}_{execution_id[:8]}",
                description={
                    "skill_id": skill.id,
                    "skill_name": skill.name,
                    "skill_type": skill.type,
                    "execution_id": execution_id,
                    "parameters": parameters,
                },
                tags=[skill.id, "experiment", "auto"],
            )

            # Save data arrays
            if isinstance(result_data, dict):
                for key, value in result_data.items():
                    try:
                        dataset.set_array(key, value)
                    except Exception as e:
                        logger.warning(f"Failed to save array {key}: {e}")
            else:
                # Save as single result
                dataset.set_array("result", result_data)

            # Save executed code as script
            if hasattr(dataset, "script"):
                dataset.script = code

            logger.info(f"Results saved to dataset: {dataset.id}")
            return dataset.id

        except Exception as e:
            logger.error(f"Failed to save results: {e}")
            return None

    def _generate_cache_key(self, skill: Skill, parameters: dict[str, Any]) -> str:
        """Generate cache key for skill + parameters.

        Args:
            skill: The skill
            parameters: Parameters

        Returns:
            Cache key string
        """
        key_data = f"{skill.id}:{sorted(parameters.items())}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
