"""History tracking for the World Model.

Provides audit trail functionality for tracking parameter changes,
experiment executions, and system events.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any

from loguru import logger


class RecordType(Enum):
    """Types of history records."""

    PARAMETER_UPDATE = auto()
    PARAMETER_DELETE = auto()
    SKILL_START = auto()
    SKILL_COMPLETE = auto()
    SKILL_ERROR = auto()
    ANALYSIS_START = auto()
    ANALYSIS_COMPLETE = auto()
    ANALYSIS_ERROR = auto()
    DEVICE_STATE_CHANGE = auto()
    EXPERIMENT_STATUS_CHANGE = auto()
    HUMAN_INTERACTION = auto()
    CONFIG_UPDATE = auto()
    LESSON_SAVED = auto()
    SYSTEM_EVENT = auto()


@dataclass
class HistoryRecord:
    """A single history record.

    Attributes:
        record_id: Unique record identifier
        type: Type of record
        timestamp: When the event occurred
        session_id: Session identifier
        source: Source component or skill
        description: Human-readable description
        data: Associated data
        tags: Optional tags for categorization
    """

    record_id: str
    type: RecordType
    timestamp: datetime
    session_id: str
    source: str
    description: str
    data: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "record_id": self.record_id,
            "type": self.type.name,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "source": self.source,
            "description": self.description,
            "data": self.data,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HistoryRecord:
        """Create from dictionary.

        Args:
            data: Dictionary data

        Returns:
            HistoryRecord instance
        """
        return cls(
            record_id=data["record_id"],
            type=RecordType[data["type"]],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            session_id=data["session_id"],
            source=data["source"],
            description=data["description"],
            data=data.get("data", {}),
            tags=data.get("tags", []),
        )


class HistoryTracker:
    """Tracks history of events and changes.

    Provides an append-only audit trail for the World Model that
can be used for debugging, analysis, and compliance.

    Example:
        ```python
        tracker = HistoryTracker(storage)

        # Record events
        tracker.record(
            type=RecordType.PARAMETER_UPDATE,
            session_id="session_123",
            source="rabi_skill",
            description="Updated qubit frequency",
            data={"path": "qubit_1.frequency", "value": 5.2e9}
        )

        # Query history
        updates = tracker.query(type=RecordType.PARAMETER_UPDATE, limit=10)
        ```
    """

    def __init__(self, storage=None, max_memory_records: int = 10000):
        """Initialize history tracker.

        Args:
            storage: Optional storage backend for persistence
            max_memory_records: Maximum records to keep in memory
        """
        self._storage = storage
        self._max_memory = max_memory_records
        self._records: list[HistoryRecord] = []
        self._record_count = 0

    def record(
        self,
        type: RecordType,
        session_id: str,
        source: str,
        description: str,
        data: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> HistoryRecord:
        """Record a history event.

        Args:
            type: Type of record
            session_id: Session identifier
            source: Source component
            description: Human-readable description
            data: Associated data
            tags: Optional tags

        Returns:
            Created HistoryRecord
        """
        import uuid

        self._record_count += 1

        record = HistoryRecord(
            record_id=str(uuid.uuid4()),
            type=type,
            timestamp=datetime.now(),
            session_id=session_id,
            source=source,
            description=description,
            data=data or {},
            tags=tags or [],
        )

        self._records.append(record)

        # Trim if needed
        if len(self._records) > self._max_memory:
            self._records = self._records[-self._max_memory :]

        # Persist if storage available
        if self._storage:
            # TODO: Implement storage persistence
            pass

        logger.debug(f"History recorded: {description}")
        return record

    def query(
        self,
        type: RecordType | None = None,
        session_id: str | None = None,
        source: str | None = None,
        tags: list[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[HistoryRecord]:
        """Query history records with filters.

        Args:
            type: Filter by record type
            session_id: Filter by session ID
            source: Filter by source
            tags: Filter by tags (must have all specified tags)
            since: Filter records after this time
            until: Filter records before this time
            limit: Maximum records to return

        Returns:
            List of matching records
        """
        results = self._records

        if type:
            results = [r for r in results if r.type == type]
        if session_id:
            results = [r for r in results if r.session_id == session_id]
        if source:
            results = [r for r in results if r.source == source]
        if tags:
            results = [r for r in results if all(t in r.tags for t in tags)]
        if since:
            results = [r for r in results if r.timestamp >= since]
        if until:
            results = [r for r in results if r.timestamp <= until]

        return results[-limit:]

    def get_session_history(self, session_id: str) -> list[HistoryRecord]:
        """Get all records for a specific session.

        Args:
            session_id: Session identifier

        Returns:
            List of records for the session
        """
        return [r for r in self._records if r.session_id == session_id]

    def get_latest(
        self,
        type: RecordType | None = None,
        session_id: str | None = None,
    ) -> HistoryRecord | None:
        """Get the latest record matching filters.

        Args:
            type: Optional type filter
            session_id: Optional session filter

        Returns:
            Latest matching record or None
        """
        records = self.query(type=type, session_id=session_id, limit=1)
        return records[0] if records else None

    def clear(self) -> None:
        """Clear all in-memory history records."""
        self._records.clear()
        logger.info("History cleared")

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about the history.

        Returns:
            Dictionary of statistics
        """
        stats = {
            "total_records": len(self._records),
            "record_count": self._record_count,
            "by_type": {},
            "by_session": {},
        }

        for record in self._records:
            type_name = record.type.name
            stats["by_type"][type_name] = stats["by_type"].get(type_name, 0) + 1

            session = record.session_id
            stats["by_session"][session] = stats["by_session"].get(session, 0) + 1

        return stats

    def export_to_dict(self) -> list[dict[str, Any]]:
        """Export all records to list of dictionaries.

        Returns:
            List of record dictionaries
        """
        return [r.to_dict() for r in self._records]

    def get_summary(self, limit: int = 20) -> str:
        """Get a human-readable summary of recent history.

        Args:
            limit: Number of recent records to include

        Returns:
            Formatted summary string
        """
        lines = ["History Summary:"]
        lines.append("-" * 40)

        if not self._records:
            lines.append("(no records)")
            return "\n".join(lines)

        stats = self.get_statistics()
        lines.append(f"Total records: {stats['total_records']}")
        lines.append(f"Unique sessions: {len(stats['by_session'])}")
        lines.append("")
        lines.append("Recent Events:")

        for record in self._records[-limit:]:
            time_str = record.timestamp.strftime("%H:%M:%S")
            lines.append(
                f"[{time_str}] {record.type.name}: {record.description}"
            )

        return "\n".join(lines)
