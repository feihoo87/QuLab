"""Base World Model class.

The World Model provides a unified view of the experimental state,
including parameters, device states, and historical records.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from .history import HistoryRecord, HistoryTracker, RecordType
from .parameter import ParameterStore, ParameterValue
from .state import ExperimentState, ExperimentStatus, StateManager


class WorldModel:
    """World Model for maintaining experimental state.

    The World Model is the central repository for all experimental
    state including:
    - Parameters with confidence levels and expiration
    - Device states and configurations
    - Experiment execution state
    - Historical audit trail

    It integrates with the storage system for persistence and
    provides a unified interface for agents to read and write state.

    Example:
        ```python
        world_model = WorldModel(storage)

        # Set a parameter
        world_model.set_parameter(
            "qubit_1.frequency",
            value=5.2e9,
            confidence=0.95,
            source="rabi_skill"
        )

        # Get a parameter
        freq = world_model.get_parameter("qubit_1.frequency")
        if freq and not freq.is_expired():
            print(f"Frequency: {freq.value} Hz")

        # Update experiment state
        world_model.set_experiment_status(ExperimentStatus.EXECUTING)
        world_model.set_current_skill("t1_measurement")

        # Record history
        world_model.record_history(
            type=RecordType.SKILL_START,
            session_id="session_123",
            description="Starting T1 measurement"
        )
        ```
    """

    def __init__(
        self,
        storage=None,
        default_ttl: float | None = None,
        auto_save: bool = True,
    ):
        """Initialize the World Model.

        Args:
            storage: Optional storage backend for persistence
            default_ttl: Default TTL in seconds for parameters
            auto_save: Whether to auto-save changes
        """
        self._storage = storage
        self._auto_save = auto_save

        # Initialize sub-components
        self.parameters = ParameterStore(storage, default_ttl)
        self.state = StateManager(storage)
        self.history = HistoryTracker(storage)

        logger.info("World Model initialized")

    # Parameter delegation methods

    def get_parameter(self, path: str, default: Any = None) -> ParameterValue | None:
        """Get a parameter value.

        Args:
            path: Dot-notation path to the parameter
            default: Default value if not found

        Returns:
            ParameterValue or default
        """
        return self.parameters.get(path, default)

    def get_parameter_value(self, path: str, default: Any = None) -> Any:
        """Get just the value of a parameter.

        Args:
            path: Dot-notation path to the parameter
            default: Default value if not found or expired

        Returns:
            Parameter value or default
        """
        return self.parameters.get_value(path, default)

    def set_parameter(
        self,
        path: str,
        value: Any,
        confidence: float,
        source: str,
        valid_for: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Set a parameter value.

        Args:
            path: Dot-notation path to the parameter
            value: The parameter value
            confidence: Confidence level (0-1)
            source: Source of the parameter
            valid_for: Validity duration in seconds
            metadata: Additional metadata
        """
        from datetime import timedelta

        # Convert seconds to timedelta if needed
        ttl = timedelta(seconds=valid_for) if valid_for else None

        self.parameters.set(
            path=path,
            value=value,
            confidence=confidence,
            source=source,
            valid_for=ttl,
            metadata=metadata,
        )

        # Record in history
        self.history.record(
            type=RecordType.PARAMETER_UPDATE,
            session_id=self._get_current_session(),
            source=source,
            description=f"Updated {path} = {value}",
            data={"path": path, "value": value, "confidence": confidence},
        )

        if self._auto_save:
            self.save()

    def delete_parameter(self, path: str) -> bool:
        """Delete a parameter.

        Args:
            path: Dot-notation path to the parameter

        Returns:
            True if deleted, False if not found
        """
        result = self.parameters.delete(path)
        if result:
            self.history.record(
                type=RecordType.PARAMETER_DELETE,
                session_id=self._get_current_session(),
                source="world_model",
                description=f"Deleted parameter {path}",
                data={"path": path},
            )
        return result

    def query_parameters(self, prefix: str | None = None) -> dict[str, ParameterValue]:
        """Query parameters by path prefix.

        Args:
            prefix: Path prefix to match

        Returns:
            Dictionary of matching parameters
        """
        return self.parameters.query(prefix)

    # State delegation methods

    def set_experiment_status(self, status: ExperimentStatus) -> None:
        """Set the experiment status.

        Args:
            status: New experiment status
        """
        old_status = self.state.get_experiment_state().status
        self.state.set_experiment_status(status)

        self.history.record(
            type=RecordType.EXPERIMENT_STATUS_CHANGE,
            session_id=self._get_current_session(),
            source="world_model",
            description=f"Status: {old_status.name} -> {status.name}",
            data={"old_status": old_status.name, "new_status": status.name},
        )

    def set_current_skill(self, skill_name: str | None) -> None:
        """Set the currently executing skill.

        Args:
            skill_name: Name of the skill
        """
        self.state.set_current_skill(skill_name)

    def set_progress(self, progress: float) -> None:
        """Set the execution progress.

        Args:
            progress: Progress percentage (0-100)
        """
        self.state.set_progress(progress)

    def get_experiment_state(self) -> ExperimentState:
        """Get the current experiment state.

        Returns:
            Current experiment state
        """
        return self.state.get_experiment_state()

    # Device delegation methods

    def update_device(self, name: str, **params) -> None:
        """Update device information.

        Args:
            name: Device name
            **params: Device parameters
        """
        from .state import DeviceState

        old_device = self.state.get_device(name)
        old_state = old_device.state if old_device else DeviceState.UNKNOWN

        device = self.state.update_device(name, **params)

        if device and device.state != old_state:
            self.history.record(
                type=RecordType.DEVICE_STATE_CHANGE,
                session_id=self._get_current_session(),
                source="world_model",
                description=f"Device {name}: {old_state.name} -> {device.state.name}",
                data={
                    "device": name,
                    "old_state": old_state.name,
                    "new_state": device.state.name,
                },
            )

    # History methods

    def record_history(
        self,
        type: RecordType,
        session_id: str,
        description: str,
        data: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> HistoryRecord:
        """Record a history event.

        Args:
            type: Type of record
            session_id: Session identifier
            description: Human-readable description
            data: Associated data
            tags: Optional tags

        Returns:
            Created HistoryRecord
        """
        return self.history.record(
            type=type,
            session_id=session_id,
            source="world_model",
            description=description,
            data=data,
            tags=tags,
        )

    def get_history(self, **kwargs) -> list[HistoryRecord]:
        """Query history records.

        Args:
            **kwargs: Query filters (see HistoryTracker.query)

        Returns:
            List of matching records
        """
        return self.history.query(**kwargs)

    # Utility methods

    def _get_current_session(self) -> str:
        """Get current session ID (placeholder).

        Returns:
            Session identifier
        """
        # TODO: Implement session tracking
        return "default"

    def save(self) -> None:
        """Save current state to storage."""
        if self._storage:
            self.parameters.save()
            # TODO: Save state and history

    def clear(self) -> None:
        """Clear all World Model data."""
        self.parameters.clear()
        self.state.reset()
        self.history.clear()
        logger.info("World Model cleared")

    def get_summary(self) -> str:
        """Get a comprehensive summary of the World Model state.

        Returns:
            Formatted summary string
        """
        lines = [
            "=" * 50,
            "WORLD MODEL SUMMARY",
            "=" * 50,
            "",
            self.state.get_summary(),
            "",
            self.parameters.get_summary(),
            "",
            self.history.get_summary(limit=10),
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert World Model state to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "parameters": self.parameters.to_dict(),
            "state": self.state.get_experiment_state().to_dict(),
            "devices": {
                name: {
                    "state": d.state.name,
                    "parameters": d.parameters,
                    "last_update": d.last_update.isoformat(),
                }
                for name, d in self.state.get_all_devices().items()
            },
        }
