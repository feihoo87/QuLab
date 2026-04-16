"""Tests for qulab.trace.client."""

import json

from qulab.trace.client import TraceClient, upload_buffer_files
from qulab.trace.models import EventType


class TestTraceClient:
    def test_init(self, tmp_buffer_dir):
        client = TraceClient(
            server_url="http://localhost:8790",
            buffer_dir=tmp_buffer_dir,
        )
        assert client.session_id
        assert client.kernel_id
        assert client.enabled

    def test_emit_writes_to_buffer_file(self, tmp_buffer_dir):
        client = TraceClient(
            buffer_dir=tmp_buffer_dir,
            local_only=True,
        )
        client.start()

        client.emit(EventType.SESSION_START, {"python_version": "3.12"})
        client.emit(EventType.CELL_EXECUTE_START, {
            "code": "x = 1", "execution_count": 1, "cell_id": "c1",
        })

        client.stop()

        # Check JSONL file was created
        jsonl_files = list(tmp_buffer_dir.glob("*.jsonl"))
        assert len(jsonl_files) == 1

        lines = jsonl_files[0].read_text("utf-8").strip().split("\n")
        assert len(lines) == 2

        event0 = json.loads(lines[0])
        assert event0["event_type"] == "session_start"
        assert event0["session_id"] == client.session_id

        event1 = json.loads(lines[1])
        assert event1["event_type"] == "cell_execute_start"
        assert event1["payload"]["code"] == "x = 1"
        assert event1["payload"]["cell_id"] == "c1"

    def test_sequence_numbers_increment(self, tmp_buffer_dir):
        client = TraceClient(
            buffer_dir=tmp_buffer_dir,
            local_only=True,
        )
        client.start()

        for i in range(5):
            client.emit(EventType.CELL_OUTPUT, {
                "content": f"out {i}", "execution_count": i,
            })

        client.stop()

        jsonl_files = list(tmp_buffer_dir.glob("*.jsonl"))
        lines = jsonl_files[0].read_text("utf-8").strip().split("\n")
        seq_nums = [json.loads(line)["sequence_no"] for line in lines]
        assert seq_nums == [1, 2, 3, 4, 5]

    def test_cell_code_history_by_cell_id(self, tmp_buffer_dir):
        client = TraceClient(buffer_dir=tmp_buffer_dir, local_only=True)
        assert client.get_cell_code_hash("cell-abc") is None

        client.record_cell_code("cell-abc", "hash_abc", "x = 1")
        assert client.get_cell_code_hash("cell-abc") == "hash_abc"
        assert client.get_cell_code("hash_abc") == "x = 1"

        # Update same cell with different code
        client.record_cell_code("cell-abc", "hash_def", "x = 2")
        assert client.get_cell_code_hash("cell-abc") == "hash_def"
        assert client.get_cell_code("hash_def") == "x = 2"

    def test_disabled_client_skips_emit(self, tmp_buffer_dir):
        client = TraceClient(
            buffer_dir=tmp_buffer_dir,
            enabled=False,
            local_only=True,
        )
        client.start()
        client.emit(EventType.SESSION_START, {})
        client.stop()

        jsonl_files = list(tmp_buffer_dir.glob("*.jsonl"))
        if jsonl_files:
            content = jsonl_files[0].read_text("utf-8").strip()
            assert content == ""


    def test_find_most_similar_code(self, tmp_buffer_dir):
        client = TraceClient(buffer_dir=tmp_buffer_dir, local_only=True)

        # Record some executions
        client.record_cell_code("k1", "h1", "x = np.linspace(0,1,100)\ny = np.sin(x)\nplt.plot(x,y)")
        client.record_cell_code("k2", "h2", "print('hello')")

        # Similar code (one parameter changed)
        new_code = "x = np.linspace(0,2,100)\ny = np.sin(x)\nplt.plot(x,y)"
        new_hash = "h3"
        result = client.find_most_similar_code(new_code, new_hash)
        assert result is not None
        assert "np.linspace(0,1,100)" in result

    def test_find_most_similar_code_no_match(self, tmp_buffer_dir):
        client = TraceClient(buffer_dir=tmp_buffer_dir, local_only=True)
        client.record_cell_code("k1", "h1", "x = 1")

        result = client.find_most_similar_code("completely different code\nnothing in common", "h2")
        assert result is None

    def test_find_most_similar_code_skips_exact(self, tmp_buffer_dir):
        client = TraceClient(buffer_dir=tmp_buffer_dir, local_only=True)
        client.record_cell_code("k1", "h1", "x = 1\ny = 2")

        # Exact same code hash - should skip
        result = client.find_most_similar_code("x = 1\ny = 2", "h1")
        assert result is None


class TestUploadBufferFiles:
    def test_no_files_returns_empty(self, tmp_buffer_dir):
        results = upload_buffer_files(tmp_buffer_dir, "http://localhost:9999")
        assert results == {}

    def test_skips_already_uploaded(self, tmp_buffer_dir):
        jsonl_file = tmp_buffer_dir / "test_session.jsonl"
        events = [
            json.dumps({"event_id": "1", "session_id": "s",
                         "event_type": "session_start",
                         "timestamp": "2026-01-01T00:00:00Z", "payload": {}}),
            json.dumps({"event_id": "2", "session_id": "s",
                         "event_type": "cell_output",
                         "timestamp": "2026-01-01T00:01:00Z", "payload": {}}),
        ]
        jsonl_file.write_text("\n".join(events) + "\n", encoding="utf-8")

        meta_file = jsonl_file.with_suffix(".meta")
        meta_file.write_text("2", encoding="utf-8")

        results = upload_buffer_files(tmp_buffer_dir, "http://localhost:9999")
        assert results == {}
