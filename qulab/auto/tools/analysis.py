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

    def figure_to_base64(self, fig=None, image_format: str = 'png', dpi: int = 150) -> str:
        """Convert matplotlib figure to base64 for LLM consumption.

        Args:
            fig: Matplotlib figure (uses current figure if None)
            image_format: Image format ('png', 'jpg', 'svg')
            dpi: Resolution for raster formats

        Returns:
            Base64 encoded image string
        """
        import matplotlib.pyplot as plt
        import io
        import base64

        if fig is None:
            fig = plt.gcf()

        buf = io.BytesIO()
        fig.savefig(buf, format=image_format, dpi=dpi, bbox_inches='tight')
        buf.seek(0)
        img_bytes = buf.getvalue()
        buf.close()

        return base64.b64encode(img_bytes).decode('utf-8')

    def create_analysis_figure(self, data_dict: dict, plot_func, **kwargs) -> dict:
        """Create a standardized analysis figure document.

        Args:
            data_dict: Dictionary containing data to plot
            plot_func: Function that takes (fig, ax, data_dict) and draws the plot
            **kwargs: Additional options:
                - figsize: Figure size tuple (default: (8, 6))
                - image_format: Image format (default: 'png')
                - dpi: Resolution (default: 150)
                - xlabel: X-axis label
                - ylabel: Y-axis label
                - title: Figure title
                - caption: Figure caption for LLM
                - extra_tags: Additional tags for the document

        Returns:
            Dictionary with document data in standard format
        """
        import matplotlib.pyplot as plt

        figsize = kwargs.get('figsize', (8, 6))
        fig, ax = plt.subplots(figsize=figsize)

        try:
            plot_func(fig, ax, data_dict)

            if 'xlabel' in kwargs:
                ax.set_xlabel(kwargs['xlabel'])
            if 'ylabel' in kwargs:
                ax.set_ylabel(kwargs['ylabel'])
            if 'title' in kwargs:
                ax.set_title(kwargs['title'])

            img_base64 = self.figure_to_base64(
                fig,
                image_format=kwargs.get('image_format', 'png'),
                dpi=kwargs.get('dpi', 150)
            )

            return {
                'data': {
                    'image': img_base64,
                    'caption': kwargs.get('caption', 'Analysis figure'),
                    'format': kwargs.get('image_format', 'png'),
                },
                'state': 'ok',
                'extracted_info': {},
                'type': 'figure',
                'tags': ['figure', 'visualization'] + kwargs.get('extra_tags', []),
            }
        finally:
            plt.close(fig)


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
            ToolResult with document IDs and results
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

            # Process result - support both new 'documents' (plural) and old format
            document_ids = []
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = custom_name or f"{skill}_{timestamp}"

            # New format: documents (plural) - list of document data
            if "documents" in result:
                documents_list = result["documents"]
                if not isinstance(documents_list, list):
                    return ToolResult(
                        error="'documents' must be a list",
                        data={"raw_result": result},
                    )

                aggregated_state = "ok"
                aggregated_extracted_info = {}

                for idx, doc_data in enumerate(documents_list):
                    doc_name = f"{base_name}_{idx}" if idx > 0 else base_name

                    # Extract fields from document data
                    doc_state = doc_data.get("state", "ok")
                    doc_extracted = doc_data.get("extracted_info", {})
                    doc_tags = doc_data.get("tags", [])
                    doc_type = doc_data.get("type", "analysis")
                    data = doc_data.get("data", doc_data)

                    # Aggregate state (error > warning > ok)
                    if doc_state == "error":
                        aggregated_state = "error"
                    elif doc_state == "warning" and aggregated_state == "ok":
                        aggregated_state = "warning"

                    # Merge extracted info with index prefix for multiple docs
                    if len(documents_list) > 1:
                        for key, value in doc_extracted.items():
                            aggregated_extracted_info[f"doc_{idx}_{key}"] = value
                    else:
                        aggregated_extracted_info.update(doc_extracted)

                    # Create document
                    doc_ref = self.storage.create_document(
                        name=doc_name,
                        data=data,
                        state=doc_state,
                        tags=(tags or [skill, "auto", "analysis"]) + doc_tags,
                        script=skill_def.code,
                        meta={
                            "skill": skill,
                            "parameters": parameters or {},
                            "dataset_ids": dataset_ids or [],
                            "extracted_info": doc_extracted,
                            "document_index": idx,
                            "document_type": doc_type,
                        },
                    )
                    document_ids.append(doc_ref.id)

                return ToolResult(
                    data={
                        "document_ids": document_ids,
                        "name": base_name,
                        "state": aggregated_state,
                        "extracted_info": aggregated_extracted_info,
                    },
                    metadata={
                        "skill": skill,
                        "parameters": parameters or {},
                        "dataset_ids": dataset_ids or [],
                    },
                )

            # Old format: direct return with data/state/extracted_info (backward compatible)
            else:
                state = result.get("state", "ok")
                extracted_info = result.get("extracted_info", {})
                data = result.get("data", result)

                doc_ref = self.storage.create_document(
                    name=base_name,
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
                document_ids.append(doc_ref.id)

                return ToolResult(
                    data={
                        "document_ids": document_ids,
                        "name": base_name,
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
