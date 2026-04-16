"""Tests for qulab.trace.models."""

from qulab.trace.models import (
    CellExecuteEndPayload,
    CellExecuteStartPayload,
    CellOutputPayload,
    CellErrorPayload,
    DisplayDataPayload,
    EventBatch,
    EventType,
    NotebookSavePayload,
    SessionStartPayload,
    SessionEndPayload,
    TraceEvent,
)


class TestEventType:
    def test_event_type_values(self):
        assert EventType.SESSION_START == "session_start"
        assert EventType.CELL_EXECUTE_START == "cell_execute_start"
        assert EventType.DISPLAY_DATA == "display_data"
        assert EventType.NOTEBOOK_SAVE == "notebook_save"

    def test_event_type_is_str(self):
        assert isinstance(EventType.SESSION_START, str)


class TestTraceEvent:
    def test_create_minimal(self):
        event = TraceEvent(
            session_id="s1",
            kernel_id="k1",
            event_type=EventType.SESSION_START,
            sequence_no=1,
            payload={"python_version": "3.12"},
        )
        assert event.session_id == "s1"
        assert event.kernel_id == "k1"
        assert event.event_type == EventType.SESSION_START
        assert event.sequence_no == 1
        assert event.event_id  # auto-generated
        assert event.timestamp  # auto-generated
        assert event.notebook_path is None
        assert event.user_id is None

    def test_auto_generated_fields(self):
        e1 = TraceEvent(
            session_id="s", kernel_id="k",
            event_type=EventType.SESSION_START,
            sequence_no=1, payload={},
        )
        e2 = TraceEvent(
            session_id="s", kernel_id="k",
            event_type=EventType.SESSION_START,
            sequence_no=2, payload={},
        )
        assert e1.event_id != e2.event_id

    def test_to_jsonl_dict(self):
        event = TraceEvent(
            session_id="s1",
            kernel_id="k1",
            event_type=EventType.CELL_EXECUTE_START,
            sequence_no=1,
            payload={"code": "x = 1"},
        )
        d = event.to_jsonl_dict()
        assert d["session_id"] == "s1"
        assert d["event_type"] == "cell_execute_start"
        assert isinstance(d["timestamp"], str)
        assert d["payload"]["code"] == "x = 1"

    def test_roundtrip_jsonl(self):
        event = TraceEvent(
            session_id="s1",
            kernel_id="k1",
            event_type=EventType.CELL_OUTPUT,
            sequence_no=5,
            payload={"content": "hello"},
            notebook_path="/tmp/test.ipynb",
            user_id="user1",
        )
        d = event.to_jsonl_dict()
        restored = TraceEvent.from_jsonl_dict(d)
        assert restored.session_id == event.session_id
        assert restored.event_type == event.event_type
        assert restored.sequence_no == event.sequence_no
        assert restored.payload == event.payload
        assert restored.notebook_path == event.notebook_path
        assert restored.user_id == event.user_id


class TestPayloadModels:
    def test_session_start(self):
        p = SessionStartPayload(python_version="3.12.0")
        assert p.python_version == "3.12.0"
        assert p.hostname == ""

    def test_session_end(self):
        p = SessionEndPayload(reason="normal", total_executions=10)
        assert p.reason == "normal"

    def test_cell_execute_start_auto_hash(self):
        p = CellExecuteStartPayload(
            execution_count=1,
            code="x = 1",
        )
        assert p.code_hash  # auto-computed
        assert len(p.code_hash) == 64  # SHA256 hex

    def test_cell_execute_start_same_code_same_hash(self):
        p1 = CellExecuteStartPayload(execution_count=1, code="x = 1")
        p2 = CellExecuteStartPayload(execution_count=2, code="x = 1")
        assert p1.code_hash == p2.code_hash

    def test_cell_execute_start_with_cell_id(self):
        p = CellExecuteStartPayload(
            cell_id="abc-123", execution_count=1, code="x = 1",
        )
        assert p.cell_id == "abc-123"

    def test_cell_execute_end(self):
        p = CellExecuteEndPayload(
            execution_count=1,
            duration_ms=150.5,
            success=True,
            output_mime_types=["text/plain", "image/png"],
            has_display_data=True,
        )
        assert p.success
        assert p.has_display_data

    def test_cell_output(self):
        p = CellOutputPayload(
            execution_count=1,
            mime_type="text/plain",
            content="hello world",
            stream="stdout",
        )
        assert p.content == "hello world"

    def test_cell_error(self):
        p = CellErrorPayload(
            execution_count=1,
            ename="ValueError",
            evalue="bad value",
            traceback_lines=["line1", "line2"],
        )
        assert p.ename == "ValueError"

    def test_display_data(self):
        p = DisplayDataPayload(
            cell_id="abc",
            execution_count=1,
            display_index=0,
            mime_bundle={"image/png": "iVBOR...", "text/plain": "<Figure>"},
        )
        assert p.mime_bundle["image/png"] == "iVBOR..."

    def test_notebook_save(self):
        p = NotebookSavePayload(
            notebook_path="test.ipynb",
            cells=[
                {"id": "c1", "cell_type": "code", "source": "x=1", "source_hash": "abc"},
                {"id": "c2", "cell_type": "markdown", "source": "# Title", "source_hash": "def"},
            ],
            cell_count=2,
            changed_cells=[{"id": "c1", "cell_type": "code", "change": "modified"}],
        )
        assert p.cell_count == 2
        assert len(p.changed_cells) == 1


class TestEventBatch:
    def test_batch_creation(self):
        events = [
            TraceEvent(
                session_id="s", kernel_id="k",
                event_type=EventType.SESSION_START,
                sequence_no=i, payload={},
            )
            for i in range(3)
        ]
        batch = EventBatch(events=events)
        assert len(batch.events) == 3
