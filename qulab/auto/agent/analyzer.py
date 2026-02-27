"""Analysis Agent for data analysis skill execution.

The Analysis Agent is responsible for:
- Parsing analysis Skill Markdown documents
- Generating Python code for data analysis
- Executing analysis code
- Structuring results according to output schemas
- Saving analysis results to Documents
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from ..bus import Event, EventType, MessageBus
from ..skills import Skill


@dataclass
class AnalysisContext:
    """Context for analysis execution.

    Attributes:
        session_id: Session identifier
        analysis_id: Unique analysis identifier
        dataset_ids: IDs of datasets to analyze
        parameters: Analysis parameters
        world_model: World model access
        config: Analysis configuration
    """

    session_id: str
    analysis_id: str
    dataset_ids: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    world_model: Any = None
    config: Any = None


@dataclass
class AnalysisResult:
    """Result of analysis execution.

    Attributes:
        status: Analysis status (success/failed)
        document_id: ID of created document (if successful)
        parameters: Extracted structured parameters
        error: Error message (if failed)
        reason: Failure reason code
        execution_time: Time taken to execute
        attempts: Number of execution attempts
        code: The executed code
    """

    status: str  # "success" | "failed"
    document_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    reason: str | None = None
    execution_time: float = 0.0
    attempts: int = 0
    code: str | None = None


class AnalysisAgent:
    """Analysis layer Agent for data analysis skills.

    The Analysis Agent parses analysis Skill Markdown documents,
    generates Python code for data analysis, and executes it.
    It structures results according to output schemas and saves
them to Documents.

    Example:
        ```python
        analyzer = AnalysisAgent(
            llm=llm_provider,
            code_generator=code_generator,
            code_executor=code_executor,
            storage=storage,
            bus=message_bus
        )

        # Analyze datasets
        result = await analyzer.analyze(
            skill=skill,
            dataset_ids=["dataset_1", "dataset_2"],
            parameters={"fit_model": "lorentzian"},
            context=analysis_context
        )

        if result.status == "success":
            print(f"Analysis saved: {result.document_id}")
            print(f"Fitted parameters: {result.parameters}")
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
        """Initialize the Analysis Agent.

        Args:
            llm: LLM provider for code fixing and structuring
            code_generator: Code generator for analysis code
            code_executor: Code executor for running code
            storage: Storage backend for documents
            bus: Optional MessageBus for events
            max_retries: Maximum retry attempts
        """
        self.llm = llm
        self.generator = code_generator
        self.executor = code_executor
        self.storage = storage
        self.bus = bus
        self.max_retries = max_retries

        logger.info("Analysis Agent initialized")

    async def analyze(
        self,
        skill: Skill,
        dataset_ids: list[str],
        parameters: dict[str, Any],
        context: AnalysisContext,
    ) -> AnalysisResult:
        """Execute an analysis skill.

        This method:
        1. Loads datasets
        2. Parses the analysis skill
        3. Generates or retrieves code
        4. Executes with retry loop
        5. Structures results
        6. Saves to document

        Args:
            skill: The analysis skill
            dataset_ids: IDs of datasets to analyze
            parameters: Analysis parameters
            context: Analysis context

        Returns:
            AnalysisResult
        """
        import uuid

        analysis_id = str(uuid.uuid4())
        start_time = time.time()

        logger.info(f"Running analysis: {skill.name} (analysis_id: {analysis_id})")

        # Publish analysis start event
        if self.bus:
            await self.bus.publish(
                Event(
                    type=EventType.ANALYSIS_START,
                    payload={
                        "analysis_id": analysis_id,
                        "skill_id": skill.id,
                        "skill_name": skill.name,
                        "dataset_ids": dataset_ids,
                        "parameters": parameters,
                    },
                    session_id=context.session_id,
                    source="analysis_agent",
                )
            )

        try:
            # 1. Load datasets
            datasets = self._load_datasets(dataset_ids)
            if not datasets:
                return AnalysisResult(
                    status="failed",
                    reason="datasets_not_found",
                    error=f"Could not load datasets: {dataset_ids}",
                    execution_time=time.time() - start_time,
                )

            # 2. Parse analysis strategy
            strategy = self._parse_strategy(skill)

            # 3. Generate or get code
            code = await self._get_code(skill, datasets, parameters, context)

            # 4. Execute with retry loop
            analysis_data = None
            final_error = None

            for attempt in range(1, self.max_retries + 1):
                logger.debug(f"Analysis attempt {attempt}/{self.max_retries}")

                try:
                    exec_result = await self.executor.execute(
                        code=code,
                        context=context,
                        timeout=getattr(context.config, "max_execution_time", 600.0),
                    )

                    if exec_result.success:
                        analysis_data = exec_result.data
                        break
                    else:
                        final_error = exec_result.error
                        logger.warning(f"Analysis failed: {final_error}")

                        if attempt < self.max_retries:
                            code = await self._fix_code(code, final_error, skill)

                except asyncio.TimeoutError:
                    final_error = "Analysis timeout"
                    logger.error(final_error)
                    break
                except Exception as e:
                    final_error = str(e)
                    logger.exception("Analysis error")
                    if attempt < self.max_retries:
                        code = await self._fix_code(code, final_error, skill)

            if analysis_data is None:
                # Publish analysis error event
                if self.bus:
                    await self.bus.publish(
                        Event(
                            type=EventType.ANALYSIS_ERROR,
                            payload={
                                "analysis_id": analysis_id,
                                "skill_id": skill.id,
                                "error": final_error,
                                "attempts": attempt,
                            },
                            session_id=context.session_id,
                            source="analysis_agent",
                        )
                    )

                return AnalysisResult(
                    status="failed",
                    reason="max_retries_exceeded",
                    error=final_error,
                    execution_time=time.time() - start_time,
                    attempts=attempt,
                    code=code,
                )

            # 5. Structure results
            structured_result = await self._structure_result(
                analysis_data, skill, strategy
            )

            # 6. Save to document
            document_id = await self._save_analysis_result(
                structured_result,
                skill,
                dataset_ids,
                parameters,
                analysis_id,
                code,
            )

            execution_time = time.time() - start_time

            # Publish analysis complete event
            if self.bus:
                await self.bus.publish(
                    Event(
                        type=EventType.ANALYSIS_COMPLETE,
                        payload={
                            "analysis_id": analysis_id,
                            "skill_id": skill.id,
                            "document_id": document_id,
                            "parameters": structured_result,
                            "execution_time": execution_time,
                        },
                        session_id=context.session_id,
                        source="analysis_agent",
                    )
                )

            logger.info(f"Analysis completed: {skill.name}")

            return AnalysisResult(
                status="success",
                document_id=document_id,
                parameters=structured_result,
                execution_time=execution_time,
                attempts=attempt,
                code=code,
            )

        except Exception as e:
            logger.exception("Unexpected error during analysis")

            # Publish analysis error event
            if self.bus:
                await self.bus.publish(
                    Event(
                        type=EventType.ANALYSIS_ERROR,
                        payload={
                            "analysis_id": analysis_id,
                            "skill_id": skill.id,
                            "error": str(e),
                        },
                        session_id=context.session_id,
                        source="analysis_agent",
                    )
                )

            return AnalysisResult(
                status="failed",
                reason="unexpected_error",
                error=str(e),
                execution_time=time.time() - start_time,
            )

    def _load_datasets(self, dataset_ids: list[str]) -> list[Any]:
        """Load datasets from storage.

        Args:
            dataset_ids: List of dataset IDs

        Returns:
            List of loaded datasets
        """
        if not self.storage:
            logger.warning("No storage configured")
            return []

        datasets = []
        for ds_id in dataset_ids:
            try:
                dataset = self.storage.get_dataset(ds_id)
                if dataset:
                    datasets.append(dataset)
                else:
                    logger.warning(f"Dataset not found: {ds_id}")
            except Exception as e:
                logger.error(f"Failed to load dataset {ds_id}: {e}")

        return datasets

    def _parse_strategy(self, skill: Skill) -> dict[str, Any]:
        """Parse the analysis strategy from skill.

        Args:
            skill: The skill to parse

        Returns:
            Strategy dictionary
        """
        strategy = {
            "description": skill.description,
            "input_schema": {},
            "output_schema": {},
        }

        # Extract from skill metadata
        if hasattr(skill, "metadata") and skill.metadata:
            strategy["input_schema"] = skill.metadata.get("inputs", [])
            strategy["output_schema"] = skill.metadata.get("outputs", [])

        if hasattr(skill, "outputs") and skill.outputs:
            strategy["output_schema"] = {
                out.name: {"type": out.type, "description": out.description}
                for out in skill.outputs
            }

        return strategy

    async def _get_code(
        self,
        skill: Skill,
        datasets: list[Any],
        parameters: dict[str, Any],
        context: AnalysisContext,
    ) -> str:
        """Get analysis code (from cache or generate).

        Args:
            skill: The skill
            datasets: Loaded datasets
            parameters: Analysis parameters
            context: Analysis context

        Returns:
            Python code string
        """
        # Check if skill has direct code
        if hasattr(skill, "generation_mode") and skill.generation_mode == "direct":
            return self._extract_code_from_skill(skill)

        # Generate code
        code = await self.generator.generate_analysis(
            skill, datasets, parameters, context
        )

        return code

    def _extract_code_from_skill(self, skill: Skill) -> str:
        """Extract code from a direct mode skill.

        Args:
            skill: The skill

        Returns:
            Python code
        """
        import re

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
        """Attempt to fix analysis code based on error.

        Args:
            code: Original code
            error: Error message
            skill: The skill being executed

        Returns:
            Fixed code
        """
        logger.info(f"Attempting to fix analysis code for error: {error[:100]}...")

        prompt = f"""The following Python analysis code for skill '{skill.name}' failed with an error.

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
                        "content": "You are an expert Python data analyst who fixes code errors.",
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
            return code

    async def _structure_result(
        self,
        analysis_data: Any,
        skill: Skill,
        strategy: dict[str, Any],
    ) -> dict[str, Any]:
        """Structure raw analysis results according to output schema.

        Args:
            analysis_data: Raw analysis data
            skill: The analysis skill
            strategy: Parsed strategy

        Returns:
            Structured result dictionary
        """
        output_schema = strategy.get("output_schema", {})

        if not output_schema or not isinstance(analysis_data, dict):
            # No schema or data already structured
            return analysis_data if isinstance(analysis_data, dict) else {"result": analysis_data}

        # If analysis_data is already structured, validate against schema
        if isinstance(analysis_data, dict):
            structured = {}

            for key, spec in output_schema.items():
                if key in analysis_data:
                    value = analysis_data[key]
                    # Add type checking/validation here if needed
                    structured[key] = value
                else:
                    # Try to extract from nested structure
                    structured[key] = self._extract_value(analysis_data, key)

            return structured

        return {"result": analysis_data}

    def _extract_value(self, data: dict[str, Any], key: str) -> Any:
        """Extract a value from data by key (handles nested keys).

        Args:
            data: Data dictionary
            key: Key to extract (supports dot notation)

        Returns:
            Extracted value or None
        """
        if "." in key:
            parts = key.split(".")
            current = data
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return None
            return current
        return data.get(key)

    async def _save_analysis_result(
        self,
        structured_result: dict[str, Any],
        skill: Skill,
        dataset_ids: list[str],
        parameters: dict[str, Any],
        analysis_id: str,
        code: str,
    ) -> str | None:
        """Save analysis results to a document.

        Args:
            structured_result: Structured analysis results
            skill: Analysis skill
            dataset_ids: Source dataset IDs
            parameters: Analysis parameters
            analysis_id: Analysis identifier
            code: Executed code

        Returns:
            Document ID or None
        """
        if not self.storage:
            logger.warning("No storage configured, results not saved")
            return None

        try:
            # Create document
            document = self.storage.create_document(
                name=f"{skill.name}_analysis_{analysis_id[:8]}",
                data={
                    "analysis_id": analysis_id,
                    "skill_id": skill.id,
                    "skill_name": skill.name,
                    "parameters": parameters,
                    "results": structured_result,
                    "source_datasets": dataset_ids,
                    "analysis_code": code,
                },
                tags=[skill.id, "analysis", "auto"],
            )

            # Link to source datasets
            for ds_id in dataset_ids:
                try:
                    document.add_dataset(ds_id)
                except Exception as e:
                    logger.warning(f"Failed to link dataset {ds_id}: {e}")

            logger.info(f"Analysis results saved to document: {document.id}")
            return document.id

        except Exception as e:
            logger.error(f"Failed to save analysis results: {e}")
            return None
