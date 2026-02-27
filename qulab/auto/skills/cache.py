"""Skill code cache management."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class SkillCodeCache:
    """Cache for generated skill code.

    Stores generated code to disk with metadata for cache invalidation.
    Cache key is based on skill name and parameters hash.
    """

    def __init__(self, cache_dir: str | None = None):
        """Initialize code cache.

        Args:
            cache_dir: Base cache directory. Defaults to ~/.qulab/skill_cache
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".qulab" / "skill_cache"
        else:
            cache_dir = Path(cache_dir).expanduser()

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_param_hash(self, parameters: dict) -> str:
        """Generate hash for parameters.

        Args:
            parameters: Skill parameters

        Returns:
            MD5 hash string of sorted JSON parameters
        """
        # Sort keys for consistent hashing
        param_str = json.dumps(parameters, sort_keys=True, default=str)
        return hashlib.md5(param_str.encode()).hexdigest()

    def _get_cache_path(self, skill_name: str, parameters: dict) -> Path:
        """Get cache file path for skill and parameters.

        Args:
            skill_name: Name of the skill
            parameters: Skill parameters

        Returns:
            Path to cache directory
        """
        param_hash = self._get_param_hash(parameters)
        skill_cache_dir = self.cache_dir / skill_name
        skill_cache_dir.mkdir(parents=True, exist_ok=True)
        return skill_cache_dir / f"{param_hash}.py"

    def _get_meta_path(self, cache_path: Path) -> Path:
        """Get metadata file path for a cache file.

        Args:
            cache_path: Path to cache file

        Returns:
            Path to metadata file
        """
        return cache_path.with_suffix(".json")

    def get(
        self,
        skill_name: str,
        parameters: dict,
        skill_mtime: float | None = None,
    ) -> str | None:
        """Get cached code if valid.

        Args:
            skill_name: Name of the skill
            parameters: Skill parameters
            skill_mtime: Modification time of skill file for invalidation

        Returns:
            Cached code or None if not found/invalid
        """
        cache_path = self._get_cache_path(skill_name, parameters)
        meta_path = self._get_meta_path(cache_path)

        if not cache_path.exists() or not meta_path.exists():
            return None

        # Check metadata for cache validity
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)

            # If skill file is newer than cache, invalidate
            if skill_mtime and metadata.get("skill_mtime", 0) < skill_mtime:
                return None

            # Check if parameters match
            cached_params = metadata.get("parameters", {})
            if cached_params != parameters:
                return None

            # Return cached code
            with open(cache_path, "r", encoding="utf-8") as f:
                return f.read()

        except (json.JSONDecodeError, IOError, KeyError):
            return None

        return None

    def set(
        self,
        skill_name: str,
        parameters: dict,
        code: str,
        skill_mtime: float | None = None,
    ) -> None:
        """Cache generated code.

        Args:
            skill_name: Name of the skill
            parameters: Skill parameters
            code: Generated code to cache
            skill_mtime: Modification time of skill file
        """
        cache_path = self._get_cache_path(skill_name, parameters)
        meta_path = self._get_meta_path(cache_path)

        # Write code
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(code)

        # Write metadata
        metadata = {
            "skill_name": skill_name,
            "parameters": parameters,
            "skill_mtime": skill_mtime,
            "generated_at": str(Path(cache_path).stat().st_mtime) if Path(cache_path).exists() else None,
        }

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    def invalidate(self, skill_name: str | None = None) -> int:
        """Invalidate cached code.

        Args:
            skill_name: If provided, only invalidate for this skill.
                       If None, invalidate all cached code.

        Returns:
            Number of cache entries invalidated
        """
        count = 0

        if skill_name:
            skill_cache_dir = self.cache_dir / skill_name
            if skill_cache_dir.exists():
                for f in skill_cache_dir.iterdir():
                    if f.suffix in (".py", ".json"):
                        f.unlink()
                        count += 1
                skill_cache_dir.rmdir()
        else:
            # Invalidate all
            for skill_dir in self.cache_dir.iterdir():
                if skill_dir.is_dir():
                    for f in skill_dir.iterdir():
                        if f.suffix in (".py", ".json"):
                            f.unlink()
                            count += 1
                    skill_dir.rmdir()

        return count

    def list_cached(self, skill_name: str | None = None) -> list[dict[str, Any]]:
        """List cached entries.

        Args:
            skill_name: If provided, only list for this skill.

        Returns:
            List of cache entry metadata
        """
        results = []

        search_dirs = [self.cache_dir / skill_name] if skill_name else list(self.cache_dir.iterdir())

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            for meta_file in search_dir.glob("*.json"):
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                        results.append(metadata)
                except (json.JSONDecodeError, IOError):
                    continue

        return results

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_size = 0
        total_files = 0
        skill_counts = {}

        for skill_dir in self.cache_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_name = skill_dir.name
            skill_files = list(skill_dir.glob("*.py"))
            skill_size = sum(f.stat().st_size for f in skill_files)

            skill_counts[skill_name] = len(skill_files)
            total_files += len(skill_files)
            total_size += skill_size

        return {
            "total_skills": len(skill_counts),
            "total_cached_files": total_files,
            "total_size_bytes": total_size,
            "cache_dir": str(self.cache_dir),
            "skill_counts": skill_counts,
        }
