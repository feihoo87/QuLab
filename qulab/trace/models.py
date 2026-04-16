"""Event data models for the trace system.

Defines the schema for all telemetry events captured from Jupyter notebooks.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


class EventType(str, Enum):
    """Types of events captured by the trace system."""

    SESSION_START = "session_start"
    SESSION_END = "session_end"
    CELL_EXECUTE_START = "cell_execute_start"
    CELL_EXECUTE_END = "cell_execute_end"
    CELL_OUTPUT = "cell_output"
    CELL_ERROR = "cell_error"
    DISPLAY_DATA = "display_data"
    NOTEBOOK_SAVE = "notebook_save"


# --- Payload models ---


class SessionStartPayload(BaseModel):
    """Payload for session_start events."""

    python_version: str
    ipython_version: str = ""
    hostname: str = ""
    qulab_version: str = ""
    notebook_path: str = ""
    kernel_info: dict = Field(default_factory=dict)


class SessionEndPayload(BaseModel):
    """Payload for session_end events."""

    reason: str = "normal"  # "normal", "error", "interrupt"
    total_executions: int = 0


class CellExecuteStartPayload(BaseModel):
    """Payload for cell_execute_start events.

    Contains full source code and diff against the previous execution
    of the same cell (identified by cell_id).
    """

    cell_id: str = ""
    execution_count: int
    code: str
    code_hash: str = ""
    diff_ops: list[dict] = Field(default_factory=list)

    def model_post_init(self, _context: object = None, /) -> None:
        if not self.code_hash:
            self.code_hash = hashlib.sha256(
                self.code.encode("utf-8")
            ).hexdigest()


class CellExecuteEndPayload(BaseModel):
    """Payload for cell_execute_end events."""

    cell_id: str = ""
    execution_count: int
    duration_ms: float
    success: bool
    output_mime_types: list[str] = Field(default_factory=list)
    has_display_data: bool = False


class CellOutputPayload(BaseModel):
    """Payload for cell_output events.

    Captures text output, display data, and stream output.
    """

    cell_id: str = ""
    execution_count: int
    mime_type: str = "text/plain"
    content: str = ""
    stream: str = ""  # "stdout", "stderr", or ""
    truncated: bool = False


class CellErrorPayload(BaseModel):
    """Payload for cell_error events."""

    cell_id: str = ""
    execution_count: int
    ename: str
    evalue: str
    traceback_lines: list[str] = Field(default_factory=list)


class DisplayDataPayload(BaseModel):
    """Payload for display_data events (figures, HTML, rich output).

    Captures display objects intercepted from IPython's display publisher,
    including matplotlib inline figures rendered before post_run_cell.
    """

    cell_id: str = ""
    execution_count: int
    display_index: int = 0
    mime_bundle: dict = Field(default_factory=dict)
    # mime_bundle keys: "image/png" (base64), "text/plain", "text/html", etc.


class NotebookSavePayload(BaseModel):
    """Payload for notebook_save events.

    Captures the full notebook cell structure on save, including
    markdown cells, cell order, and content changes.
    """

    notebook_path: str
    cells: list[dict] = Field(default_factory=list)
    # Each cell: {"id": str, "cell_type": str, "source": str, "source_hash": str}
    cell_count: int = 0
    changed_cells: list[dict] = Field(default_factory=list)
    # Each: {"id": str, "cell_type": str, "change": "modified"|"added"|"removed"}


# --- Event envelope ---


PAYLOAD_TYPES: dict[EventType, type[BaseModel]] = {
    EventType.SESSION_START: SessionStartPayload,
    EventType.SESSION_END: SessionEndPayload,
    EventType.CELL_EXECUTE_START: CellExecuteStartPayload,
    EventType.CELL_EXECUTE_END: CellExecuteEndPayload,
    EventType.CELL_OUTPUT: CellOutputPayload,
    EventType.CELL_ERROR: CellErrorPayload,
    EventType.DISPLAY_DATA: DisplayDataPayload,
    EventType.NOTEBOOK_SAVE: NotebookSavePayload,
}


class TraceEvent(BaseModel):
    """Common envelope for all trace events."""

    event_id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=_utcnow)
    session_id: str
    kernel_id: str
    notebook_path: Optional[str] = None
    user_id: Optional[str] = None
    event_type: EventType
    sequence_no: int
    payload: dict

    def to_jsonl_dict(self) -> dict:
        """Convert to a dict suitable for JSONL serialization."""
        data = self.model_dump(mode="json")
        if isinstance(self.timestamp, str):
            data["timestamp"] = self.timestamp
        else:
            data["timestamp"] = self.timestamp.isoformat()  # pylint: disable=no-member
        return data

    @classmethod
    def from_jsonl_dict(cls, data: dict) -> TraceEvent:
        """Reconstruct from a JSONL dict."""
        return cls.model_validate(data)


class EventBatch(BaseModel):
    """A batch of events for bulk upload."""

    events: list[TraceEvent]
