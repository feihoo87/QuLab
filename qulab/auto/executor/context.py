"""Execution context for code execution.

Defines the context passed to code executors containing
all necessary information and dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionContext:
    """Context for code execution.

    This context is passed to the code executor and provides:
    - Access to the world model for parameter retrieval
    - Access to storage for data loading/saving
    - Execution metadata (session, execution IDs)
    - Configuration options

    Attributes:
        session_id: Session identifier
        execution_id: Execution identifier
        parameters: Execution parameters
        world_model: World model access
        storage: Storage access
        config: Execution configuration
        metadata: Additional metadata
    """

    session_id: str
    execution_id: str
    parameters: dict[str, Any] = field(default_factory=dict)
    world_model: Any = None
    storage: Any = None
    config: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_parameter(self, path: str, default: Any = None) -> Any:
        """Get a parameter value from world model.

        Args:
            path: Parameter path
            default: Default value if not found

        Returns:
            Parameter value or default
        """
        if self.world_model:
            param = self.world_model.get_parameter(path)
            if param and not param.is_expired():
                return param.value
        return default

    def set_parameter(
        self,
        path: str,
        value: Any,
        confidence: float = 1.0,
        source: str | None = None,
    ) -> None:
        """Set a parameter value in world model.

        Args:
            path: Parameter path
            value: Parameter value
            confidence: Confidence level (0-1)
            source: Source of the parameter
        """
        if self.world_model:
            self.world_model.set_parameter(
                path=path,
                value=value,
                confidence=confidence,
                source=source or f"execution_{self.execution_id}",
            )

    def load_dataset(self, dataset_id: str) -> Any:
        """Load a dataset from storage.

        Args:
            dataset_id: Dataset identifier

        Returns:
            Dataset object or None
        """
        if self.storage:
            return self.storage.get_dataset(dataset_id)
        return None

    def create_dataset(self, name: str, **kwargs) -> Any:
        """Create a new dataset in storage.

        Args:
            name: Dataset name
            **kwargs: Additional dataset parameters

        Returns:
            Created dataset or None
        """
        if self.storage:
            return self.storage.create_dataset(name=name, **kwargs)
        return None
