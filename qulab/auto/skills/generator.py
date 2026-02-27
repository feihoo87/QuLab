"""Code generator for skills using LLM."""

from typing import TYPE_CHECKING

from .cache import SkillCodeCache

if TYPE_CHECKING:
    from ..llm.base import LLMProvider
    from .base import Skill


CODE_GENERATION_PROMPT = """You are a professional quantum experiment code generation expert. Please generate Python code according to the following guide.

## Skill Description
{skill_description}

## Skill Type
{skill_type}

## Input Parameters
{inputs}

## Expected Output
{outputs}

## Code Generation Guide
{guide_content}

## Execution Context
{context}

Please generate a Python function that meets the following requirements:
1. Function signature: def run({params}, ctx=None):
2. Return value must be a dictionary containing 'dataset' or 'datasets' and output parameters
3. Can use numpy (np) and ctx object
4. Code must be complete and runnable
5. Include proper docstring with parameter descriptions
6. Handle edge cases and input validation

Only return Python code, no explanations.
"""

CODE_FIX_PROMPT = """Please fix the following code that has errors.

## Original Code
```python
{code}
```

## Error Information
{error}

## Error Type
{error_type}

## Skill Description
{skill_description}

## Code Generation Guide
{guide_content}

Please fix the code and return the complete corrected version. Only return code, no explanations.
"""


class CodeGenerator:
    """Generate skill code using LLM based on guide content."""

    def __init__(self, llm: "LLMProvider", cache: SkillCodeCache | None = None):
        """Initialize code generator.

        Args:
            llm: LLM provider for code generation
            cache: Optional code cache for storing generated code
        """
        self.llm = llm
        self.cache = cache or SkillCodeCache()

    def _build_params_signature(self, inputs: list[dict]) -> str:
        """Build function parameter signature from inputs.

        Args:
            inputs: List of input parameter definitions

        Returns:
            Parameter signature string
        """
        params = []
        for inp in inputs:
            name = inp.get("name", "")
            param_type = inp.get("type", "any")
            default = inp.get("default", None)

            if default is not None:
                if isinstance(default, str):
                    params.append(f'{name}: str = "{default}"')
                else:
                    params.append(f"{name}: {param_type} = {default}")
            else:
                params.append(f"{name}: {param_type}")

        return ", ".join(params)

    def _format_inputs(self, inputs: list[dict]) -> str:
        """Format inputs for prompt.

        Args:
            inputs: List of input parameter definitions

        Returns:
            Formatted input description
        """
        lines = []
        for inp in inputs:
            name = inp.get("name", "")
            param_type = inp.get("type", "any")
            desc = inp.get("description", "")
            default = inp.get("default", None)
            required = inp.get("required", True)

            req_str = "required" if required and default is None else "optional"
            default_str = f", default: {default}" if default is not None else ""

            lines.append(f"- {name} ({param_type}, {req_str}{default_str}): {desc}")

        return "\n".join(lines) if lines else "None"

    def _format_outputs(self, outputs: list[dict]) -> str:
        """Format outputs for prompt.

        Args:
            outputs: List of output parameter definitions

        Returns:
            Formatted output description
        """
        lines = []
        for out in outputs:
            name = out.get("name", "")
            param_type = out.get("type", "any")
            desc = out.get("description", "")
            lines.append(f"- {name} ({param_type}): {desc}")

        return "\n".join(lines) if lines else "None"

    def _build_context_info(self, skill_type: str) -> str:
        """Build context information for code generation.

        Args:
            skill_type: Type of skill (measurement or analysis)

        Returns:
            Context description string
        """
        if skill_type == "measurement":
            return """Available context (ctx):
- ctx.get_instrument(name): Get instrument by name (e.g., 'mw_source', 'readout_card')
- ctx.storage: Storage instance for data persistence

Return format:
{
    'dataset': {
        'x': x_data_array,
        'y': y_data_array,
        ...
    },
    'output_param1': value1,
    'output_param2': value2,
}
Or for multiple datasets:
{
    'datasets': [
        {'x': x1, 'y': y1, ...},
        {'x': x2, 'y': y2, ...},
    ],
    'output_param1': value1,
}"""
        elif skill_type == "analysis":
            return """Available context (ctx):
- ctx.datasets: List of dataset wrappers with dict-like access
- ctx.get_dataset(index): Get dataset by index
- ctx.figure_to_base64(fig): Convert matplotlib figure to base64
- ctx.create_analysis_figure(data_dict, plot_func, **kwargs): Create standardized figure

Return format:
{
    'documents': [
        {
            'type': 'figure',
            'state': 'ok',
            'data': {...},
            'extracted_info': {'param1': value1, ...},
            'tags': ['tag1', 'tag2'],
        },
    ],
    'extracted_info': {'param1': value1, 'param2': value2},
}
"""
        return ""

    async def generate(
        self,
        skill: "Skill",
        parameters: dict,
        force_regenerate: bool = False,
    ) -> str:
        """Generate code for a skill.

        Args:
            skill: Skill definition
            parameters: Parameters for the skill
            force_regenerate: Force regeneration even if cache exists

        Returns:
            Generated Python code
        """
        # Check cache first
        skill_mtime = skill.filepath.stat().st_mtime if skill.filepath else None

        if not force_regenerate:
            cached_code = self.cache.get(skill.name, parameters, skill_mtime)
            if cached_code:
                return cached_code

        # Build prompt
        prompt = CODE_GENERATION_PROMPT.format(
            skill_description=skill.description,
            skill_type=skill.type,
            inputs=self._format_inputs(skill.inputs),
            outputs=self._format_outputs(skill.outputs),
            guide_content=skill.guide_content,
            context=self._build_context_info(skill.type),
            params=self._build_params_signature(skill.inputs),
        )

        # Call LLM
        messages = [
            {"role": "system", "content": "You are an expert quantum experiment code generator. Generate clean, correct Python code."},
            {"role": "user", "content": prompt},
        ]

        response = await self.llm.chat(messages)

        # Extract code from response
        code = response.content or ""

        # Clean up code (remove markdown code blocks if present)
        code = self._extract_code(code)

        # Cache the generated code
        self.cache.set(skill.name, parameters, code, skill_mtime)

        return code

    async def fix(
        self,
        skill: "Skill",
        code: str,
        error: str,
        parameters: dict,
        error_type: str = "runtime",
    ) -> str:
        """Fix code based on error information.

        Args:
            skill: Skill definition
            code: Original code that failed
            error: Error message
            parameters: Parameters used
            error_type: Type of error (syntax, runtime, logic)

        Returns:
            Fixed code
        """
        # Build prompt
        prompt = CODE_FIX_PROMPT.format(
            code=code,
            error=error,
            error_type=error_type,
            skill_description=skill.description,
            guide_content=skill.guide_content,
        )

        # Call LLM
        messages = [
            {"role": "system", "content": "You are an expert Python debugger. Fix the code based on the error."},
            {"role": "user", "content": prompt},
        ]

        response = await self.llm.chat(messages)

        # Extract code from response
        fixed_code = response.content or ""

        # Clean up code
        fixed_code = self._extract_code(fixed_code)

        # Update cache with fixed code
        skill_mtime = skill.filepath.stat().st_mtime if skill.filepath else None
        self.cache.set(skill.name, parameters, fixed_code, skill_mtime)

        return fixed_code

    def _extract_code(self, content: str) -> str:
        """Extract Python code from markdown content.

        Args:
            content: Content that may contain markdown code blocks

        Returns:
            Extracted Python code
        """
        import re

        # Look for Python code blocks
        pattern = r"```python\n(.*?)\n```"
        matches = re.findall(pattern, content, re.DOTALL)

        if matches:
            return "\n\n".join(matches)

        # If no Python code blocks, look for any code blocks
        pattern = r"```\n(.*?)\n```"
        matches = re.findall(pattern, content, re.DOTALL)

        if matches:
            return "\n\n".join(matches)

        # If no code blocks, return entire content
        return content.strip()
