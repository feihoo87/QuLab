"""Experiment state management for the World Model.

Provides tracking of experiment state including device states,
current operation, and execution context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any

from loguru import logger


class ExperimentStatus(Enum):
    """Status of an experiment execution."""

    IDLE = auto()
    PLANNING = auto()
    EXECUTING = auto()
    ANALYZING = auto()
    PAUSED = auto()  # Waiting for human input
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class DeviceState(Enum):
    """State of a device/instrument."""

    UNKNOWN = auto()
    OFFLINE = auto()
    INITIALIZING = auto()
    READY = auto()
    BUSY = auto()
    ERROR = auto()


@dataclass
class DeviceInfo:
    """Information about a device state.

    Attributes:
        name: Device name
        state: Current device state
        parameters: Device-specific parameters
        last_update: Last update timestamp
        error_message: Error message if in ERROR state
    """

    name: str
    state: DeviceState = DeviceState.UNKNOWN
    parameters: dict[str, Any] = field(default_factory=dict)
    last_update: datetime = field(default_factory=datetime.now)
    error_message: str | None = None

    def update_state(self, new_state: DeviceState, **params) -> None:
        """Update device state.

        Args:
            new_state: New device state
            **params: Additional device parameters to update
        """
        self.state = new_state
        self.parameters.update(params)
        self.last_update = datetime.now()
        logger.debug(f"Device {self.name} state updated to {new_state.name}")


@dataclass
class ExperimentState:
    """Current state of an experiment execution.

    Attributes:
        status: Current experiment status
        current_skill: Currently executing skill (if any)
        current_step: Current step in the execution
        progress: Progress percentage (0-100)
        start_time: When the experiment started
        estimated_end: Estimated completion time
        context: Additional context information
    """

    status: ExperimentStatus = ExperimentStatus.IDLE
    current_skill: str | None = None
    current_step: str | None = None
    progress: float = 0.0
    start_time: datetime | None = None
    estimated_end: datetime | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "status": self.status.name,
            "current_skill": self.current_skill,
            "current_step": self.current_step,
            "progress": self.progress,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "estimated_end": self.estimated_end.isoformat() if self.estimated_end else None,
            "context": self.context,
        }


class StateManager:
    """Manages experiment state and device states.

    Provides a centralized way to track the current state of
    experiments and connected devices.

    Example:
        ```python
        manager = StateManager()

        # Update experiment state
        manager.set_experiment_status(ExperimentStatus.EXECUTING)
        manager.set_current_skill("rabi_measurement")
        manager.set_progress(50)

        # Track device state
        manager.update_device("awg_1", DeviceState.BUSY, frequency=5.2e9)

        # Get current state
        state = manager.get_experiment_state()
        ```
    """

    def __init__(self, storage=None):
        """Initialize state manager.

        Args:
            storage: Optional storage backend for persistence
        """
        self._storage = storage
        self._experiment = ExperimentState()
        self._devices: dict[str, DeviceInfo] = {}
        self._history: list[dict[str, Any]] = []

    # Experiment state methods

    def set_experiment_status(self, status: ExperimentStatus) -> None:
        """Set the experiment status.

        Args:
            status: New experiment status
        """
        old_status = self._experiment.status
        self._experiment.status = status

        if status == ExperimentStatus.EXECUTING and old_status != ExperimentStatus.EXECUTING:
            self._experiment.start_time = datetime.now()

        self._record_state_change("status", old_status.name, status.name)
        logger.info(f"Experiment status changed: {old_status.name} -> {status.name}")

    def set_current_skill(self, skill_name: str | None) -> None:
        """Set the currently executing skill.

        Args:
            skill_name: Name of the skill, or None to clear
        """
        old_skill = self._experiment.current_skill
        self._experiment.current_skill = skill_name
        self._record_state_change("current_skill", old_skill, skill_name)

    def set_current_step(self, step: str | None) -> None:
        """Set the current execution step.

        Args:
            step: Description of current step, or None to clear
        """
        old_step = self._experiment.current_step
        self._experiment.current_step = step
        self._record_state_change("current_step", old_step, step)

    def set_progress(self, progress: float) -> None:
        """Set the execution progress.

        Args:
            progress: Progress percentage (0-100)
        """
        self._experiment.progress = max(0.0, min(100.0, progress))

    def set_context(self, **kwargs) -> None:
        """Set context information.

        Args:
            **kwargs: Context key-value pairs
        """
        self._experiment.context.update(kwargs)

    def clear_context(self) -> None:
        """Clear all context information."""
        self._experiment.context.clear()

    def get_experiment_state(self) -> ExperimentState:
        """Get the current experiment state.

        Returns:
            Current experiment state
        """
        return self._experiment

    def is_idle(self) -> bool:
        """Check if experiment is idle.

        Returns:
            True if idle
        """
        return self._experiment.status == ExperimentStatus.IDLE

    def is_running(self) -> bool:
        """Check if experiment is running.

        Returns:
            True if executing or analyzing
        """
        return self._experiment.status in (
            ExperimentStatus.EXECUTING,
            ExperimentStatus.ANALYZING,
            ExperimentStatus.PLANNING,
        )

    def is_paused(self) -> bool:
        """Check if experiment is paused waiting for input.

        Returns:
            True if paused
        """
        return self._experiment.status == ExperimentStatus.PAUSED

    # Device state methods

    def register_device(self, name: str, **params) -> DeviceInfo:
        """Register a new device.

        Args:
            name: Device name
            **params: Initial device parameters

        Returns:
            DeviceInfo instance
        """
        device = DeviceInfo(name=name, parameters=params)
        self._devices[name] = device
        logger.debug(f"Registered device: {name}")
        return device

    def update_device(
        self, name: str, state: DeviceState | None = None, **params
    ) -> DeviceInfo | None:
        """Update device state and/or parameters.

        Args:
            name: Device name
            state: New device state (optional)
            **params: Device parameters to update

        Returns:
            Updated DeviceInfo or None if device not found
        """
        if name not in self._devices:
            self.register_device(name)

        device = self._devices[name]

        if state is not None:
            device.update_state(state, **params)
        elif params:
            device.parameters.update(params)
            device.last_update = datetime.now()

        return device

    def set_device_error(self, name: str, error_message: str) -> None:
        """Set device to error state.

        Args:
            name: Device name
            error_message: Error description
        """
        if name not in self._devices:
            self.register_device(name)

        device = self._devices[name]
        device.state = DeviceState.ERROR
        device.error_message = error_message
        device.last_update = datetime.now()
        logger.error(f"Device {name} error: {error_message}")

    def get_device(self, name: str) -> DeviceInfo | None:
        """Get device information.

        Args:
            name: Device name

        Returns:
            DeviceInfo or None if not found
        """
        return self._devices.get(name)

    def get_all_devices(self) -> dict[str, DeviceInfo]:
        """Get all registered devices.

        Returns:
            Dictionary of device name to DeviceInfo
        """
        return dict(self._devices)

    def list_devices(self, state: DeviceState | None = None) -> list[str]:
        """List device names.

        Args:
            state: Filter by state (optional)

        Returns:
            List of device names
        """
        if state is None:
            return list(self._devices.keys())
        return [name for name, d in self._devices.items() if d.state == state]

    def remove_device(self, name: str) -> bool:
        """Remove a device.

        Args:
            name: Device name

        Returns:
            True if removed, False if not found
        """
        if name in self._devices:
            del self._devices[name]
            return True
        return False

    # History methods

    def _record_state_change(self, field: str, old_value: Any, new_value: Any) -> None:
        """Record a state change in history.

        Args:
            field: Field that changed
            old_value: Previous value
            new_value: New value
        """
        self._history.append({
            "timestamp": datetime.now().isoformat(),
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
        })

    def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get state change history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of state change records
        """
        return self._history[-limit:]

    def clear_history(self) -> None:
        """Clear state change history."""
        self._history.clear()

    # Summary methods

    def get_summary(self) -> str:
        """Get a human-readable summary of current state.

        Returns:
            Formatted summary string
        """
        lines = ["Experiment State:"]
        lines.append("-" * 40)

        exp = self._experiment
        lines.append(f"Status: {exp.status.name}")

        if exp.current_skill:
            lines.append(f"Current Skill: {exp.current_skill}")
        if exp.current_step:
            lines.append(f"Current Step: {exp.current_step}")
        if exp.progress > 0:
            lines.append(f"Progress: {exp.progress:.1f}%")

        lines.append("")
        lines.append("Devices:")

        if self._devices:
            for name, device in sorted(self._devices.items()):
                status_icon = "✓" if device.state == DeviceState.READY else "✗"
                lines.append(f"  {status_icon} {name}: {device.state.name}")
                if device.error_message:
                    lines.append(f"    Error: {device.error_message}")
        else:
            lines.append("  (no devices registered)")

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all state to initial values."""
        self._experiment = ExperimentState()
        self._devices.clear()
        self._history.clear()
        logger.info("State manager reset")
