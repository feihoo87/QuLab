"""Measurement tool for executing measurement skills."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from .base import BaseTool, ToolResult

if TYPE_CHECKING:
    from qulab.storage import Storage

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
    """Execute measurement skills."""

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
    }

    def __init__(self, storage: "Storage", skill_loader: "SkillLoader"):
        """Initialize measurement tool.

        Args:
            storage: Storage instance
            skill_loader: Skill loader
        """
        self.storage = storage
        self.skill_loader = skill_loader

    async def execute(
        self,
        skill: str,
        parameters: dict | None = None,
        tags: list[str] | None = None,
        custom_name: str | None = None,
    ) -> ToolResult:
        """Execute measurement skill.

        Args:
            skill: Skill name
            parameters: Skill parameters
            tags: Dataset tags
            custom_name: Custom dataset name

        Returns:
            ToolResult with dataset IDs and outputs
        """
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

            # Create context
            ctx = MeasurementContext(self.storage)

            # Execute skill code
            result = self._execute_skill(skill_def.code, parameters or {}, ctx)

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
                        script=skill_def.code,
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
                    script=skill_def.code,
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
                    script=skill_def.code,
                )
                dataset_ids.append(dataset_ref.id)
                outputs = result

            return ToolResult(
                data={
                    "dataset_ids": dataset_ids,
                    "name": base_name,
                    "outputs": outputs,
                },
                metadata={"skill": skill, "parameters": parameters or {}},
            )

        except KeyError as e:
            return ToolResult(error=f"Skill not found: {e}")
        except Exception as e:
            return ToolResult(error=f"Measurement failed: {str(e)}")

    def _execute_skill(self, code: str, parameters: dict, ctx: MeasurementContext) -> dict:
        """Execute skill code.

        Args:
            code: Python code to execute
            parameters: Parameters to pass
            ctx: Measurement context

        Returns:
            Execution result
        """
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
                ds.attrs[key] = value
