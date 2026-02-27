"""Analysis tool for executing analysis skills."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from .base import BaseTool, ToolResult

if TYPE_CHECKING:
    from qulab.storage import Storage

    from ..skills.base import Skill
    from ..skills.cache import SkillCodeCache
    from ..skills.generator import CodeGenerator
    from ..skills.loader import SkillLoader


class DatasetWrapper:
    """Wrapper for Dataset to provide dict-like access."""

    def __init__(self, dataset: Any):
        """Initialize wrapper.

        Args:
            dataset: Dataset instance to wrap
        """
        self._dataset = dataset
        self._cache: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get value by key (array or attr).

        Args:
            key: Array name or attr name
            default: Default value if not found

        Returns:
            Array data or attr value
        """
        # Check cache first
        if key in self._cache:
            return self._cache[key]

        # Try to get as array
        try:
            import numpy as np
            arr = self._dataset.get_array(key)
            value = arr[:]
            self._cache[key] = value
            return value
        except KeyError:
            pass

        # Try to get as attr
        try:
            attrs = self._dataset.attrs
            if key in attrs:
                return attrs[key]
        except Exception:
            pass

        return default

    def __getitem__(self, key: str) -> Any:
        """Get item by key."""
        result = self.get(key)
        if result is None and key not in self._dataset.attrs:
            raise KeyError(key)
        return result

    def __contains__(self, key: str) -> bool:
        """Check if key exists."""
        return self.get(key) is not None

    def keys(self) -> list[str]:
        """Get all available keys."""
        return self._dataset.keys()


class AnalysisContext:
    """Context passed to analysis skill code."""

    def __init__(self, storage: "Storage", datasets: list[Any]):
        """Initialize analysis context.

        Args:
            storage: Storage instance
            datasets: List of loaded datasets
        """
        self.storage = storage
        # Wrap datasets for dict-like access
        self.datasets = [DatasetWrapper(ds) for ds in datasets]

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
    """Execute analysis skills with code generation support."""

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
        """Initialize analysis tool.

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
        dataset_ids: list[int] | None = None,
        tags: list[str] | None = None,
        custom_name: str | None = None,
        force_regenerate: bool = False,
        max_retries: int | None = None,
    ) -> ToolResult:
        """Execute analysis skill.

        Args:
            skill: Skill name
            parameters: Skill parameters
            dataset_ids: Dataset IDs to analyze
            tags: Document tags
            custom_name: Custom document name
            force_regenerate: Force code regeneration even if cached
            max_retries: Override default max retries for error recovery

        Returns:
            ToolResult with document IDs and results
        """
        max_retries = max_retries if max_retries is not None else self.max_retries

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

            # Get or generate code
            code = await self._get_or_generate_code(
                skill_def, parameters or {}, force_regenerate
            )

            # Create context
            ctx = AnalysisContext(self.storage, datasets)

            # Execute skill code with retry
            result, executed_code = await self._execute_with_retry(
                code, parameters or {}, ctx, skill_def, max_retries
            )

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
                        script=executed_code,
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

                # Build LLM-friendly summary from extracted_info
                llm_summary = self._build_llm_summary(aggregated_extracted_info)

                return ToolResult(
                    data={
                        "document_ids": document_ids,
                        "name": base_name,
                        "state": aggregated_state,
                        "summary": llm_summary,  # LLM-friendly summary
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
                    script=executed_code,
                    meta={
                        "skill": skill,
                        "parameters": parameters or {},
                        "dataset_ids": dataset_ids or [],
                        "extracted_info": extracted_info,
                    },
                )
                document_ids.append(doc_ref.id)

                # Build LLM-friendly summary from extracted_info
                llm_summary = self._build_llm_summary(extracted_info)

                return ToolResult(
                    data={
                        "document_ids": document_ids,
                        "name": base_name,
                        "state": state,
                        "summary": llm_summary,  # LLM-friendly summary
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
        ctx: AnalysisContext,
        skill_def: "Skill",
        max_retries: int,
    ) -> tuple[dict, str]:
        """Execute skill code with error retry and regeneration.

        Args:
            code: Python code to execute
            parameters: Parameters to pass
            ctx: Analysis context
            skill_def: Skill definition for error feedback
            max_retries: Maximum number of retries

        Returns:
            Tuple of (execution result, executed code)

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

    def _build_llm_summary(self, extracted_info: dict) -> dict:
        """Build LLM-friendly summary from extracted info, filtering out large data.

        Args:
            extracted_info: Raw extracted info from analysis

        Returns:
            Filtered info with only scalar/numeric values and small strings
        """
        import json
        import numpy as np

        summary = {}
        for key, value in extracted_info.items():
            # Skip None values
            if value is None:
                continue
            # Include scalar numeric values and small strings
            if isinstance(value, (int, float, bool)):
                summary[key] = value
            elif isinstance(value, str):
                # Include short strings (< 500 chars)
                if len(value) < 500:
                    summary[key] = value
                else:
                    summary[key] = value[:500] + "... [truncated]"
            elif isinstance(value, np.integer):
                summary[key] = int(value)
            elif isinstance(value, np.floating):
                summary[key] = float(value)
            elif isinstance(value, np.ndarray) and value.size == 1:
                summary[key] = value.item()
            # Skip arrays and large objects
            elif isinstance(value, (list, np.ndarray)):
                # Include list length as info
                summary[key] = f"[{len(value)} items]"
            elif isinstance(value, dict):
                # Recursively process small dicts
                try:
                    json_str = json.dumps(value)
                    if len(json_str) < 1000:
                        summary[key] = value
                    else:
                        summary[key] = "{... large object ...}"
                except (TypeError, ValueError):
                    summary[key] = "{... non-serializable ...}"
            else:
                # Try to include other scalar types
                try:
                    json.dumps({key: value})
                    summary[key] = value
                except (TypeError, ValueError):
                    continue
        return summary

    def _execute_skill(self, code: str, parameters: dict, ctx: AnalysisContext) -> dict:
        """Execute skill code.

        Args:
            code: Python code to execute
            parameters: Parameters to pass
            ctx: Analysis context

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
