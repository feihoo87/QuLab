"""Session data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto


class SessionStatus(Enum):
    """Session execution status."""

    IDLE = auto()
    RUNNING = auto()
    PAUSED_HUMAN = auto()  # Waiting for human input
    PAUSED_CONFIG = auto()  # Waiting for config confirmation
    COMPLETED = auto()
    ERROR = auto()


@dataclass
class SessionState:
    """Current session state."""

    session_id: str
    status: SessionStatus = SessionStatus.IDLE
    current_iteration: int = 0
    max_iterations: int = 40
    last_message: str | None = None
    pending_question: str | None = None
    pending_options: list[str] | None = None
    pending_config_updates: dict | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "status": self.status.name,
            "current_iteration": self.current_iteration,
            "max_iterations": self.max_iterations,
            "last_message": self.last_message,
            "pending_question": self.pending_question,
            "pending_options": self.pending_options,
            "pending_config_updates": self.pending_config_updates,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        """Create from dictionary."""
        status = SessionStatus[data.get("status", "IDLE")]

        created_at = data.get("created_at")
        if created_at:
            created_at = datetime.fromisoformat(created_at)

        updated_at = data.get("updated_at")
        if updated_at:
            updated_at = datetime.fromisoformat(updated_at)

        return cls(
            session_id=data.get("session_id", ""),
            status=status,
            current_iteration=data.get("current_iteration", 0),
            max_iterations=data.get("max_iterations", 40),
            last_message=data.get("last_message"),
            pending_question=data.get("pending_question"),
            pending_options=data.get("pending_options"),
            pending_config_updates=data.get("pending_config_updates"),
            created_at=created_at or datetime.now(),
            updated_at=updated_at or datetime.now(),
        )
