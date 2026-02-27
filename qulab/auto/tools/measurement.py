"""Measurement tool for executing measurement skills."""

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .base import BaseTool, ToolResult

if TYPE_CHECKING:
    from qulab.storage import Storage

    from ..skills.base import Skill
    from ..skills.cache import SkillCodeCache
    from ..skills.generator import CodeGenerator
    from ..skills.loader import SkillLoader


class MeasurementContext:
    """Context passed to measurement skill code."""

    def __init__(self, storage: "Storage"):
        """Initialize measurement context.

        Args:
            storage: Storage instance
        """
        self.storage = storage
        self._instruments: dict[str, Any] = {}

    def get_instrument(self, name: str) -> Any:
        """Get instrument by name.

        Args:
            name: Instrument name

        Returns:
            Instrument instance

        Raises:
            KeyError: If instrument not found
        """
        if name not in self._instruments:
            raise KeyError(f"Instrument not found: {name}")
        return self._instruments[name]

    def register_instrument(self, name: str, instrument: Any) -> None:
        """Register an instrument.

        Args:
            name: Instrument name
            instrument: Instrument instance
        """
        self._instruments[name] = instrument


class MeasurementTool(BaseTool):
    """Execute measurement skills with code generation support."""

    name = "run_measurement"
    description = "Execute a measurement task using a skill. Results are saved as a Dataset."

    parameters = {
        "skill": {
            "type": "string",
            "description": "Name of the measurement skill to execute",
            "required": True,
        },
        "parameters": {
            "type": "object",
            "description": "Parameters for the skill",
            "default": {},
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Tags to apply to the resulting dataset",
            "default": ["auto"],
        },
        "custom_name": {
            "type": "string",
            "description": "Custom name for the dataset (optional)",
        },
        "force_regenerate": {
            "type": "boolean",
            "description": "Force code regeneration even if cached",
            "default": False,
        },
        "max_retries": {
            "type": "integer",
            "description": "Maximum retries on execution error",
            "default": 3,
        },
    }

    def __init__(
        self,
        storage: "Storage",
        skill_loader: "SkillLoader",
        code_generator: "CodeGenerator | None" = None,
        max_retries: int = 3,
    ):
        """Initialize measurement tool.

        Args:
            storage: Storage instance
            skill_loader: Skill loader
            code_generator: Optional code generator for dynamic skill generation
            max_retries: Maximum number of retries on execution error
        """
        self.storage = storage
        self.skill_loader = skill_loader
        self.code_generator = code_generator
        self.max_retries = max_retries

    async def execute(
        self,
        skill: str,
        parameters: dict | None = None,
        tags: list[str] | None = None,
        custom_name: str | None = None,
        force_regenerate: bool = False,
        max_retries: int | None = None,
    ) -> ToolResult:
        """Execute measurement skill.

        Args:
            skill: Skill name
            parameters: Skill parameters
            tags: Dataset tags
            custom_name: Custom dataset name
            force_regenerate: Force code regeneration even if cached
            max_retries: Override default max retries for error recovery

        Returns:
            ToolResult with dataset IDs and outputs
        """
        max_retries = max_retries if max_retries is not None else self.max_retries

        try:
            # Load skill
            skill_def = self.skill_loader.get(skill)

            if skill_def.type != "measurement":
                return ToolResult(
                    error=f"Skill {skill} is not a measurement skill (type: {skill_def.type})"
                )

            # Validate inputs
            errors = skill_def.validate_inputs(parameters or {})
            if errors:
                return ToolResult(error=f"Input validation failed: {', '.join(errors)}")

            # Get or generate code
            code = await self._get_or_generate_code(
                skill_def, parameters or {}, force_regenerate
            )

            # Create context
            ctx = MeasurementContext(self.storage)

            # Execute skill code with retry
            result, executed_code = await self._execute_with_retry(
                code, parameters or {}, ctx, skill_def, max_retries
            )

            # Process result - support both new 'datasets' (plural) and old 'dataset' (singular)
            dataset_ids = []
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = custom_name or f"{skill}_{timestamp}"

            # New format: datasets (plural) - list of dataset data
            if "datasets" in result:
                datasets_list = result["datasets"]
                if not isinstance(datasets_list, list):
                    return ToolResult(
                        error="'datasets' must be a list",
                        data={"raw_result": result},
                    )

                for idx, ds_data in enumerate(datasets_list):
                    ds_name = f"{base_name}_{idx}" if idx > 0 else base_name
                    dataset_ref = self.storage.create_dataset(
                        name=ds_name,
                        description={
                            "skill": skill,
                            "parameters": parameters or {},
                            "type": "auto_measurement",
                            "index": idx,
                        },
                        tags=tags or [skill, "auto"],
                        script=executed_code,
                    )

                    try:
                        ds = dataset_ref.get()
                        self._populate_dataset(ds, ds_data)
                        ds.flush()
                        dataset_ids.append(dataset_ref.id)
                    except Exception as e:
                        return ToolResult(
                            error=f"Failed to populate dataset {idx}: {e}",
                            data={"dataset_ids": dataset_ids, "raw_result": result},
                        )

                outputs = {k: v for k, v in result.items() if k != "datasets"}

            # Old format: dataset (singular) - single dataset data (backward compatible)
            elif "dataset" in result:
                dataset_ref = self.storage.create_dataset(
                    name=base_name,
                    description={
                        "skill": skill,
                        "parameters": parameters or {},
                        "type": "auto_measurement",
                    },
                    tags=tags or [skill, "auto"],
                    script=executed_code,
                )

                try:
                    ds = dataset_ref.get()
                    self._populate_dataset(ds, result["dataset"])
                    ds.flush()
                    dataset_ids.append(dataset_ref.id)
                except Exception as e:
                    return ToolResult(
                        error=f"Failed to populate dataset: {e}",
                        data={"dataset_ids": dataset_ids, "raw_result": result},
                    )

                outputs = {k: v for k, v in result.items() if k != "dataset"}

            else:
                # No dataset returned - still create a record
                dataset_ref = self.storage.create_dataset(
                    name=base_name,
                    description={
                        "skill": skill,
                        "parameters": parameters or {},
                        "type": "auto_measurement",
                    },
                    tags=tags or [skill, "auto"],
                    script=executed_code,
                )
                dataset_ids.append(dataset_ref.id)
                outputs = result

            # Build summary for LLM - only include scalar values, filter out large data
            llm_summary = self._build_llm_summary(outputs)

            return ToolResult(
                data={
                    "dataset_ids": dataset_ids,
                    "name": base_name,
                    "summary": llm_summary,  # LLM-friendly summary
                },
                metadata={"skill": skill, "parameters": parameters or {}},
            )

        except KeyError as e:
            return ToolResult(error=f"Skill not found: {e}")
        except Exception as e:
            return ToolResult(error=f"Measurement failed: {str(e)}")

    def _build_llm_summary(self, outputs: dict) -> dict:
        """Build LLM-friendly summary from outputs, filtering out large arrays.

        Args:
            outputs: Raw outputs from skill

        Returns:
            Filtered outputs with only scalar/numeric values
        """
        import numpy as np

        summary = {}
        for key, value in outputs.items():
            # Skip None values
            if value is None:
                continue
            # Include scalar numeric values and strings
            if isinstance(value, (int, float, str, bool)):
                summary[key] = value
            elif isinstance(value, np.integer):
                summary[key] = int(value)
            elif isinstance(value, np.floating):
                summary[key] = float(value)
            elif isinstance(value, np.ndarray) and value.size == 1:
                summary[key] = value.item()
            # Skip arrays and large objects
            elif isinstance(value, (list, np.ndarray, dict)):
                continue
            else:
                # Try to include other scalar types
                try:
                    # Test if JSON serializable and not too large
                    json.dumps({key: value})
                    summary[key] = value
                except (TypeError, ValueError):
                    continue
        return summary

    async def _get_or_generate_code(
        self,
        skill_def: "Skill",
        parameters: dict,
        force_regenerate: bool,
    ) -> str:
        """Get code for skill, generating if necessary.

        Args:
            skill_def: Skill definition
            parameters: Parameters for the skill
            force_regenerate: Force code regeneration

        Returns:
            Python code to execute

        Raises:
            RuntimeError: If code generation is needed but no generator available
        """
        # Direct mode: use the code directly
        if skill_def.generation_mode == "direct":
            if not skill_def.code:
                raise RuntimeError(f"Direct mode skill {skill_def.name} has no code")
            return skill_def.code

        # Code generation mode: need a code generator
        if self.code_generator is None:
            raise RuntimeError(
                f"Skill {skill_def.name} requires code generation but no code generator provided"
            )

        # Generate or retrieve cached code
        return await self.code_generator.generate(
            skill_def, parameters, force_regenerate=force_regenerate
        )

    async def _execute_with_retry(
        self,
        code: str,
        parameters: dict,
        ctx: MeasurementContext,
        skill_def: "Skill",
        max_retries: int,
    ) -> tuple[dict, str]:
        """Execute skill code with error retry and regeneration.

        Args:
            code: Python code to execute
            parameters: Parameters to pass
            ctx: Measurement context
            skill_def: Skill definition for error feedback
            max_retries: Maximum number of retries

        Returns:
            Execution result

        Raises:
            RuntimeError: If all retries fail
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                result = self._execute_skill(code, parameters, ctx)
                return result, code
            except SyntaxError as e:
                # Syntax error - must regenerate code
                last_error = f"SyntaxError: {e}"
                if (
                    attempt < max_retries - 1
                    and skill_def.generation_mode == "code"
                    and self.code_generator
                ):
                    code = await self.code_generator.fix(
                        skill_def, code, str(e), parameters, error_type="syntax"
                    )
                else:
                    raise
            except (NameError, AttributeError, TypeError, KeyError) as e:
                # Runtime error - try to fix
                last_error = f"{type(e).__name__}: {e}"
                if (
                    attempt < max_retries - 1
                    and skill_def.generation_mode == "code"
                    and self.code_generator
                ):
                    code = await self.code_generator.fix(
                        skill_def, code, str(e), parameters, error_type="runtime"
                    )
                else:
                    raise
            except Exception as e:
                # Other errors - don't retry
                raise

        # Should not reach here, but just in case
        raise RuntimeError(f"Failed after {max_retries} attempts. Last error: {last_error}")

    def _execute_skill(self, code: str, parameters: dict, ctx: MeasurementContext) -> dict:
        """Execute skill code.

        Args:
            code: Python code to execute
            parameters: Parameters to pass
            ctx: Measurement context

        Returns:
            Execution result
        """
        if not code:
            raise RuntimeError("No code to execute")

        # Create namespace with standard imports
        namespace = {
            "np": __import__("numpy"),
            "ctx": ctx,
            "__name__": "__skill__",
        }

        # Execute code
        exec(code, namespace)  # pylint: disable=exec-used

        # Find and call run function
        if "run" not in namespace:
            raise RuntimeError("Skill code must define a 'run' function")

        run_func = namespace["run"]

        # Call with parameters
        result = run_func(**parameters, ctx=ctx)

        if not isinstance(result, dict):
            raise RuntimeError("Skill 'run' function must return a dictionary")

        return result

    def _populate_dataset(self, ds: Any, data: dict) -> None:
        """Populate dataset with data.

        Args:
            ds: Dataset instance
            data: Data dictionary with arrays
        """
        import numpy as np

        for key, value in data.items():
            if isinstance(value, np.ndarray):
                ds.set_array(key, value)
            elif isinstance(value, list):
                ds.set_array(key, np.array(value))
            elif isinstance(value, (int, float, str)):
                ds.set_attr(key, value)
