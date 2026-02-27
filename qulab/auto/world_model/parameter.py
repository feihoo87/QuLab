"""Parameter management for the World Model.

Provides storage and retrieval of experimental parameters with
confidence levels, timestamps, and expiration tracking.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

from loguru import logger


@dataclass
class ParameterValue:
    """A parameter value with metadata.

    Attributes:
        value: The actual parameter value
        confidence: Confidence level (0-1)
        timestamp: When the parameter was set
        source: Source of the parameter (skill_id, "human", "calibration", etc.)
        valid_for: Optional validity duration
        metadata: Additional metadata
    """

    value: Any
    confidence: float
    timestamp: datetime
    source: str
    valid_for: timedelta | None = None
    metadata: dict[str, Any] | None = None

    def is_expired(self) -> bool:
        """Check if the parameter value has expired.

        Returns:
            True if expired, False otherwise
        """
        if self.valid_for is None:
            return False
        return datetime.now() - self.timestamp > self.valid_for

    def age(self) -> timedelta:
        """Get the age of this parameter value.

        Returns:
            Time since the parameter was set
        """
        return datetime.now() - self.timestamp

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        return {
            "value": self.value,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "valid_for": self.valid_for.total_seconds() if self.valid_for else None,
            "metadata": self.metadata or {},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParameterValue:
        """Create from dictionary.

        Args:
            data: Dictionary data

        Returns:
            ParameterValue instance
        """
        valid_for = None
        if data.get("valid_for"):
            valid_for = timedelta(seconds=data["valid_for"])

        return cls(
            value=data["value"],
            confidence=data["confidence"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data["source"],
            valid_for=valid_for,
            metadata=data.get("metadata", {}),
        )


class ParameterStore:
    """Storage for experimental parameters with hierarchical paths.

    Supports dot-notation paths like "qubit_1.frequency" or
    "resonator.Q1.frequency_GHz".

    Example:
        ```python
        store = ParameterStore(storage)

        # Set a parameter
        store.set("qubit_1.frequency", 5.2e9, confidence=0.95, source="rabi_skill")

        # Get a parameter
        param = store.get("qubit_1.frequency")
        print(param.value)  # 5200000000.0
        print(param.confidence)  # 0.95

        # Query all parameters under a path
        qubit_params = store.query("qubit_1")
        ```
    """

    def __init__(self, storage=None, default_ttl: float | None = None):
        """Initialize parameter store.

        Args:
            storage: Optional storage backend for persistence
            default_ttl: Default TTL in seconds for new parameters
        """
        self._storage = storage
        self._default_ttl = default_ttl
        self._params: dict[str, ParameterValue] = {}
        self._dirty: set[str] = set()

    def _split_path(self, path: str) -> list[str]:
        """Split a dot-notation path into components.

        Args:
            path: Dot-notation path like "qubit_1.frequency"

        Returns:
            List of path components
        """
        return path.split(".")

    def _join_path(self, parts: list[str]) -> str:
        """Join path components into a dot-notation path.

        Args:
            parts: Path components

        Returns:
            Dot-notation path
        """
        return ".".join(parts)

    def set(
        self,
        path: str,
        value: Any,
        confidence: float,
        source: str,
        valid_for: timedelta | float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Set a parameter value.

        Args:
            path: Dot-notation path to the parameter
            value: The parameter value
            confidence: Confidence level (0-1)
            source: Source of the parameter
            valid_for: Validity duration (timedelta or seconds), None for no expiration
            metadata: Additional metadata
        """
        if isinstance(valid_for, (int, float)):
            valid_for = timedelta(seconds=valid_for)
        elif valid_for is None and self._default_ttl:
            valid_for = timedelta(seconds=self._default_ttl)

        param = ParameterValue(
            value=value,
            confidence=max(0.0, min(1.0, confidence)),
            timestamp=datetime.now(),
            source=source,
            valid_for=valid_for,
            metadata=metadata,
        )

        self._params[path] = param
        self._dirty.add(path)

        logger.debug(f"Set parameter {path} = {value} (confidence: {confidence:.2f})")

    def get(self, path: str, default: Any = None) -> ParameterValue | None:
        """Get a parameter value.

        Args:
            path: Dot-notation path to the parameter
            default: Default value if parameter not found

        Returns:
            ParameterValue or default
        """
        param = self._params.get(path)

        if param is None:
            # Try to load from storage
            if self._storage:
                loaded = self._load_from_storage(path)  # pylint: disable=assignment-from-none
                if loaded is not None:
                    param = loaded
                    self._params[path] = param  # pylint: disable=unsupported-assignment-operation

        if param is None:
            return default

        return param

    def get_value(self, path: str, default: Any = None) -> Any:
        """Get just the value of a parameter.

        Args:
            path: Dot-notation path to the parameter
            default: Default value if parameter not found or expired

        Returns:
            Parameter value or default
        """
        param = self.get(path)
        if param is None or param.is_expired():
            return default
        return param.value

    def delete(self, path: str) -> bool:
        """Delete a parameter.

        Args:
            path: Dot-notation path to the parameter

        Returns:
            True if parameter was deleted, False if not found
        """
        if path in self._params:
            del self._params[path]
            self._dirty.discard(path)
            logger.debug(f"Deleted parameter {path}")
            return True
        return False

    def query(self, prefix: str | None = None, include_expired: bool = False) -> dict[str, ParameterValue]:
        """Query parameters matching a path prefix.

        Args:
            prefix: Path prefix to match, None for all parameters
            include_expired: Whether to include expired parameters

        Returns:
            Dictionary of matching parameters
        """
        results = {}

        for path, param in self._params.items():
            if prefix and not path.startswith(prefix):
                continue
            if not include_expired and param.is_expired():
                continue
            results[path] = param

        return results

    def list_paths(self, prefix: str | None = None) -> list[str]:
        """List all parameter paths.

        Args:
            prefix: Optional path prefix to filter by

        Returns:
            List of parameter paths
        """
        if prefix is None:
            return list(self._params.keys())
        return [p for p in self._params.keys() if p.startswith(prefix)]

    def get_confident_value(
        self, path: str, min_confidence: float = 0.5, default: Any = None
    ) -> Any:
        """Get parameter value only if confidence meets threshold.

        Args:
            path: Dot-notation path to the parameter
            min_confidence: Minimum confidence threshold
            default: Default value if not found or confidence too low

        Returns:
            Parameter value or default
        """
        param = self.get(path)
        if param is None or param.is_expired() or param.confidence < min_confidence:
            return default
        return param.value

    def update_confidence(self, path: str, new_confidence: float) -> bool:
        """Update the confidence of an existing parameter.

        Args:
            path: Dot-notation path to the parameter
            new_confidence: New confidence value

        Returns:
            True if updated, False if parameter not found
        """
        param = self._params.get(path)
        if param is None:
            return False

        param.confidence = max(0.0, min(1.0, new_confidence))
        self._dirty.add(path)
        return True

    def clear(self) -> None:
        """Clear all parameters from memory."""
        self._params.clear()
        self._dirty.clear()

    def save(self) -> None:
        """Save dirty parameters to storage."""
        if not self._storage or not self._dirty:
            return

        # This would save to a document in storage
        # Implementation depends on storage API
        for path in self._dirty:
            param = self._params[path]
            # TODO: Implement storage save
            pass

        self._dirty.clear()

    def _load_from_storage(self, path: str) -> ParameterValue | None:
        """Load a parameter from storage.

        Args:
            path: Parameter path

        Returns:
            ParameterValue or None
        """
        # TODO: Implement storage load
        del path  # Unused for now
        return None

    def get_all(self, include_expired: bool = False) -> dict[str, ParameterValue]:
        """Get all parameters.

        Args:
            include_expired: Whether to include expired parameters

        Returns:
            Dictionary of all parameters
        """
        if include_expired:
            return dict(self._params)
        return {k: v for k, v in self._params.items() if not v.is_expired()}

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Convert all parameters to dictionary.

        Returns:
            Nested dictionary of parameters
        """
        result: dict[str, Any] = {}

        for path, param in self._params.items():
            parts = self._split_path(path)
            current = result

            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            current[parts[-1]] = param.to_dict()

        return result

    def get_summary(self) -> str:
        """Get a human-readable summary of parameters.

        Returns:
            Formatted summary string
        """
        lines = ["World Model Parameters:"]
        lines.append("-" * 40)

        for path, param in sorted(self._params.items()):
            status = "✓" if not param.is_expired() else "✗"
            age_str = self._format_age(param.age())
            lines.append(
                f"{status} {path}: {param.value} "
                f"(conf: {param.confidence:.2f}, age: {age_str}, src: {param.source})"
            )

        return "\n".join(lines)

    def _format_age(self, age: timedelta) -> str:
        """Format a timedelta as a human-readable string.

        Args:
            age: Time delta

        Returns:
            Formatted string
        """
        total_seconds = int(age.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            return f"{total_seconds // 60}m"
        elif total_seconds < 86400:
            return f"{total_seconds // 3600}h"
        else:
            return f"{total_seconds // 86400}d"
