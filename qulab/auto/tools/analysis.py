"""Analysis tool for executing analysis skills."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from .base import BaseTool, ToolResult

if TYPE_CHECKING:
    from qulab.storage import Storage

    from ..skills.loader import SkillLoader


class AnalysisContext:
    """Context passed to analysis skill code."""

    def __init__(self, storage: "Storage", datasets: list[Any]):
        """Initialize analysis context.

        Args:
            storage: Storage instance
            datasets: List of loaded datasets
        """
        self.storage = storage
        self.datasets = datasets

    def get_dataset(self, index: int) -> Any:
        """Get dataset by index.

        Args:
            index: Dataset index in the input list

        Returns:
            Dataset instance

        Raises:
            IndexError: If index out of range
        """
        if index < 0 or index >= len(self.datasets):
            raise IndexError(f"Dataset index {index} out of range")
        return self.datasets[index]


class AnalysisTool(BaseTool):
    """Execute analysis skills."""

    name = "run_analysis"
    description = "Execute an analysis task using a skill. Results are saved as a Document."

    parameters = {
        "skill": {
            "type": "string",
            "description": "Name of the analysis skill to execute",
            "required": True,
        },
        "parameters": {
            "type": "object",
            "description": "Parameters for the skill",
            "default": {},
        },
        "dataset_ids": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "IDs of datasets to analyze",
            "default": [],
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Tags to apply to the resulting document",
            "default": ["auto", "analysis"],
        },
        "custom_name": {
            "type": "string",
            "description": "Custom name for the document (optional)",
        },
    }

    def __init__(self, storage: "Storage", skill_loader: "SkillLoader"):
        """Initialize analysis tool.

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
        dataset_ids: list[int] | None = None,
        tags: list[str] | None = None,
        custom_name: str | None = None,
    ) -> ToolResult:
        """Execute analysis skill.

        Args:
            skill: Skill name
            parameters: Skill parameters
            dataset_ids: Dataset IDs to analyze
            tags: Document tags
            custom_name: Custom document name

        Returns:
            ToolResult with document ID and results
        """
        try:
            # Load skill
            skill_def = self.skill_loader.get(skill)

            if skill_def.type != "analysis":
                return ToolResult(
                    error=f"Skill {skill} is not an analysis skill (type: {skill_def.type})"
                )

            # Load datasets
            datasets = []
            for ds_id in dataset_ids or []:
                try:
                    ds = self.storage.get_dataset(ds_id)
                    datasets.append(ds)
                except KeyError:
                    return ToolResult(error=f"Dataset not found: {ds_id}")

            # Create context
            ctx = AnalysisContext(self.storage, datasets)

            # Execute skill code
            result = self._execute_skill(skill_def.code, parameters or {}, ctx)

            # Create document
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = custom_name or f"{skill}_{timestamp}"

            # Determine state and extracted info
            state = result.get("state", "ok")
            extracted_info = result.get("extracted_info", {})
            data = result.get("data", result)

            doc_ref = self.storage.create_document(
                name=name,
                data=data,
                state=state,
                tags=tags or [skill, "auto", "analysis"],
                script=skill_def.code,
                meta={
                    "skill": skill,
                    "parameters": parameters or {},
                    "dataset_ids": dataset_ids or [],
                    "extracted_info": extracted_info,
                },
            )

            return ToolResult(
                data={
                    "document_id": doc_ref.id,
                    "name": name,
                    "state": state,
                    "extracted_info": extracted_info,
                },
                metadata={
                    "skill": skill,
                    "parameters": parameters or {},
                    "dataset_ids": dataset_ids or [],
                },
            )

        except KeyError as e:
            return ToolResult(error=f"Skill not found: {e}")
        except Exception as e:
            return ToolResult(error=f"Analysis failed: {str(e)}")

    def _execute_skill(self, code: str, parameters: dict, ctx: AnalysisContext) -> dict:
        """Execute skill code.

        Args:
            code: Python code to execute
            parameters: Parameters to pass
            ctx: Analysis context

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
