"""Skill loader for parsing and loading skill files."""

import re
from pathlib import Path
from typing import Any

import yaml

from .base import Skill


class SkillLoader:
    """Skill loader for YAML frontmatter + Markdown skill files."""

    SEARCH_PATHS = [
        "~/.qulab/skills",              # User custom skills
        "./skills",                      # Project local
        str(Path(__file__).parent / "builtin"),  # Built-in
    ]

    def __init__(self, additional_paths: list[str | Path] | None = None):
        """Initialize skill loader.

        Args:
            additional_paths: Additional paths to search for skills
        """
        self.search_paths = [Path(p).expanduser() for p in self.SEARCH_PATHS]

        if additional_paths:
            for path in additional_paths:
                expanded = Path(path).expanduser()
                if expanded not in self.search_paths:
                    self.search_paths.insert(0, expanded)

        self._skills: dict[str, Skill] = {}
        self._loaded = False

    def load_all(self, force_reload: bool = False) -> dict[str, Skill]:
        """Load all skills from search paths.

        Args:
            force_reload: Force reload even if already loaded

        Returns:
            Dictionary of loaded skills by name
        """
        if self._loaded and not force_reload:
            return self._skills.copy()

        self._skills = {}

        for path in self.search_paths:
            if not path.exists():
                continue

            # Look for SKILL.md files in subdirectories
            for skill_file in path.rglob("SKILL.md"):
                try:
                    skill = self._parse_skill(skill_file)
                    if skill.name in self._skills:
                        # Later paths override earlier ones
                        pass
                    self._skills[skill.name] = skill
                except (ValueError, yaml.YAMLError) as e:
                    # Log error but continue loading other skills
                    print(f"Error loading skill from {skill_file}: {e}")

        self._loaded = True
        return self._skills.copy()

    def get(self, name: str) -> Skill:
        """Get a skill by name.

        Args:
            name: Skill name

        Returns:
            Skill instance

        Raises:
            KeyError: If skill not found
        """
        if not self._loaded:
            self.load_all()

        if name not in self._skills:
            raise KeyError(f"Skill not found: {name}")

        return self._skills[name]

    def list_skills(self, skill_type: str | None = None) -> list[str]:
        """List available skill names.

        Args:
            skill_type: Filter by type ("measurement" or "analysis")

        Returns:
            List of skill names
        """
        if not self._loaded:
            self.load_all()

        skills = self._skills.values()

        if skill_type:
            skills = [s for s in skills if s.type == skill_type]

        return sorted([s.name for s in skills])

    def build_summary(self) -> str:
        """Build a summary of all skills for LLM context.

        Returns:
            Formatted summary string
        """
        if not self._loaded:
            self.load_all()

        lines = ["# Available Skills\n"]

        # Group by type
        measurements = [s for s in self._skills.values() if s.type == "measurement"]
        analyses = [s for s in self._skills.values() if s.type == "analysis"]

        if measurements:
            lines.append("## Measurement Skills\n")
            for skill in sorted(measurements, key=lambda s: s.name):
                lines.append(f"- **{skill.name}**: {skill.description.strip()[:100]}...")
            lines.append("")

        if analyses:
            lines.append("## Analysis Skills\n")
            for skill in sorted(analyses, key=lambda s: s.name):
                lines.append(f"- **{skill.name}**: {skill.description.strip()[:100]}...")
            lines.append("")

        return "\n".join(lines)

    def _parse_skill(self, filepath: Path) -> Skill:
        """Parse a skill file.

        Args:
            filepath: Path to SKILL.md file

        Returns:
            Parsed Skill instance

        Raises:
            ValueError: If file format is invalid
        """
        content = filepath.read_text(encoding="utf-8")

        # Split frontmatter and markdown
        frontmatter, markdown = self._split_frontmatter(content)

        # Parse YAML frontmatter
        try:
            yaml_metadata = yaml.safe_load(frontmatter) if frontmatter else {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML frontmatter: {e}")

        # Get generation mode
        # If not specified, detect based on content:
        # - Has code blocks and no explicit guide -> "direct" (backward compatible)
        # - No code blocks -> "code" (need generation)
        code = self._extract_code(markdown)
        generation_mode = yaml_metadata.get("generation_mode", "direct" if code else "code")

        # Build skill based on generation mode
        if generation_mode == "direct":
            # Direct execution mode - code must be provided
            if not code:
                raise ValueError(f"Direct mode skill {filepath} must contain Python code blocks")
            guide_content = yaml_metadata.get("guide_content", "")
        else:
            # Code generation mode (default) - guide content is the markdown
            # If there's code, it's treated as example/reference
            guide_content = markdown.strip() if not code else self._extract_guide_content(markdown, code)
            # code is optional in code mode (will be generated)
            if not code:
                code = None

        return Skill(
            name=yaml_metadata.get("name", filepath.parent.name),
            type=yaml_metadata.get("type", "unknown"),
            description=yaml_metadata.get("description", ""),
            capabilities=yaml_metadata.get("capabilities", {}),
            inputs=yaml_metadata.get("inputs", []),
            outputs=yaml_metadata.get("outputs", []),
            metadata=yaml_metadata.get("metadata", {}),
            generation_mode=generation_mode,
            guide_content=guide_content,
            code=code,
            filepath=filepath,
        )

    def _split_frontmatter(self, content: str) -> tuple[str, str]:
        """Split YAML frontmatter from markdown content.

        Args:
            content: Full file content

        Returns:
            Tuple of (frontmatter, markdown)
        """
        # Check for --- at start
        if not content.startswith("---"):
            return "", content

        # Find end of frontmatter (the next --- on its own line)
        match = re.search(r"^---\s*$", content[3:], re.MULTILINE)
        if not match:
            return "", content

        # match.start() is the position of --- in content[3:]
        frontmatter = content[3:3 + match.start()].strip()
        markdown = content[3 + match.end():].strip()

        return frontmatter, markdown

    def _extract_code(self, markdown: str) -> str:
        """Extract Python code from markdown.

        Args:
            markdown: Markdown content

        Returns:
            Extracted Python code
        """
        # Find Python code blocks
        pattern = r"```python\n(.*?)\n```"
        matches = re.findall(pattern, markdown, re.DOTALL)

        if matches:
            return "\n\n".join(matches)

        # If no code blocks, return empty string (code generation mode)
        return ""

    def _extract_guide_content(self, markdown: str, code: str) -> str:
        """Extract guide content by removing code blocks from markdown.

        Args:
            markdown: Markdown content
            code: Extracted code

        Returns:
            Guide content (markdown without code blocks)
        """
        # Remove Python code blocks to get guide content
        guide = re.sub(r"```python\n(.*?)\n```", "", markdown, flags=re.DOTALL)
        # Clean up extra whitespace
        guide = re.sub(r"\n{3,}", "\n\n", guide)
        return guide.strip()

    def add_search_path(self, path: str | Path) -> None:
        """Add a search path.

        Args:
            path: Path to add
        """
        expanded = Path(path).expanduser()
        if expanded not in self.search_paths:
            self.search_paths.insert(0, expanded)
            self._loaded = False  # Mark for reload
