"""Tests for qulab.trace.storage."""

import json
from pathlib import Path

from qulab.trace.storage import TraceStore


class TestTraceStore:
    def test_init_creates_dirs_and_db(self, tmp_data_path):
        store = TraceStore(tmp_data_path)
        assert (tmp_data_path / "events").is_dir()
        assert (tmp_data_path / "trace.db").exists()
        store.close()

    def test_write_events(self, tmp_data_path):
        store = TraceStore(tmp_data_path)

        events = [
            {
                "event_id": "e1",
                "timestamp": "2026-04-16T10:00:00Z",
                "session_id": "s1",
                "kernel_id": "k1",
                "notebook_path": "/tmp/test.ipynb",
                "user_id": "user1",
                "event_type": "session_start",
                "sequence_no": 1,
                "payload": {"python_version": "3.12"},
            },
            {
                "event_id": "e2",
                "timestamp": "2026-04-16T10:00:01Z",
                "session_id": "s1",
                "kernel_id": "k1",
                "notebook_path": "/tmp/test.ipynb",
                "user_id": "user1",
                "event_type": "cell_execute_start",
                "sequence_no": 2,
                "payload": {"code": "x = 1", "execution_count": 1},
            },
        ]

        count = store.write_events(events)
        assert count == 2

        # Check JSONL file
        jsonl_files = list((tmp_data_path / "events").glob("*.jsonl"))
        assert len(jsonl_files) == 1
        lines = jsonl_files[0].read_text("utf-8").strip().split("\n")
        assert len(lines) == 2

        store.close()

    def test_query_sessions(self, tmp_data_path):
        store = TraceStore(tmp_data_path)

        events = [
            {
                "event_id": "e1",
                "timestamp": "2026-04-16T10:00:00Z",
                "session_id": "s1",
                "kernel_id": "k1",
                "user_id": "user1",
                "notebook_path": "test.ipynb",
                "event_type": "session_start",
                "sequence_no": 1,
                "payload": {},
            },
            {
                "event_id": "e2",
                "timestamp": "2026-04-16T11:00:00Z",
                "session_id": "s2",
                "kernel_id": "k2",
                "user_id": "user2",
                "notebook_path": "other.ipynb",
                "event_type": "session_start",
                "sequence_no": 1,
                "payload": {},
            },
        ]
        store.write_events(events)

        result = store.query_sessions()
        assert result["total"] == 2
        assert len(result["sessions"]) == 2

        # Filter by user
        result = store.query_sessions(user_id="user1")
        assert result["total"] == 1
        assert result["sessions"][0]["session_id"] == "s1"

        store.close()

    def test_query_events(self, tmp_data_path):
        store = TraceStore(tmp_data_path)

        events = [
            {
                "event_id": f"e{i}",
                "timestamp": f"2026-04-16T10:00:0{i}Z",
                "session_id": "s1",
                "kernel_id": "k1",
                "user_id": "",
                "notebook_path": "",
                "event_type": "cell_execute_start" if i % 2 == 0 else "cell_execute_end",
                "sequence_no": i,
                "payload": {"execution_count": i},
            }
            for i in range(5)
        ]
        store.write_events(events)

        # Query all
        result = store.query_events(session_id="s1")
        assert result["total"] == 5

        # Query by type
        result = store.query_events(
            session_id="s1", event_type="cell_execute_start"
        )
        assert result["total"] == 3  # i=0,2,4

        store.close()

    def test_export_training_data(self, tmp_data_path):
        store = TraceStore(tmp_data_path)

        events = [
            {
                "event_id": f"e{i}",
                "timestamp": f"2026-04-16T10:00:0{i}Z",
                "session_id": "s1",
                "kernel_id": "k1",
                "user_id": "user1",
                "notebook_path": "test.ipynb",
                "event_type": "cell_execute_start",
                "sequence_no": i,
                "payload": {"code": f"x = {i}", "execution_count": i},
            }
            for i in range(3)
        ]
        store.write_events(events)

        traces = store.export_training_data()
        assert len(traces) == 1
        assert traces[0]["session_id"] == "s1"
        assert len(traces[0]["events"]) == 3
        assert traces[0]["notebook_path"] == "test.ipynb"

        store.close()

    def test_get_stats(self, tmp_data_path):
        store = TraceStore(tmp_data_path)

        events = [
            {
                "event_id": "e1",
                "timestamp": "2026-04-16T10:00:00Z",
                "session_id": "s1",
                "kernel_id": "k1",
                "user_id": "",
                "notebook_path": "",
                "event_type": "session_start",
                "sequence_no": 1,
                "payload": {},
            },
        ]
        store.write_events(events)

        stats = store.get_stats()
        assert stats["total_sessions"] == 1
        assert stats["total_events"] == 1
        assert stats["jsonl_files"] == 1
        assert stats["total_size_bytes"] > 0

        store.close()

    def test_session_update_on_multiple_batches(self, tmp_data_path):
        store = TraceStore(tmp_data_path)

        # First batch
        store.write_events([{
            "event_id": "e1",
            "timestamp": "2026-04-16T10:00:00Z",
            "session_id": "s1",
            "kernel_id": "k1",
            "user_id": "",
            "notebook_path": "",
            "event_type": "session_start",
            "sequence_no": 1,
            "payload": {},
        }])

        # Second batch with notebook_path
        store.write_events([{
            "event_id": "e2",
            "timestamp": "2026-04-16T10:05:00Z",
            "session_id": "s1",
            "kernel_id": "k1",
            "user_id": "",
            "notebook_path": "test.ipynb",
            "event_type": "cell_execute_start",
            "sequence_no": 2,
            "payload": {"code": "x=1", "execution_count": 1},
        }])

        result = store.query_sessions()
        assert result["total"] == 1
        session = result["sessions"][0]
        assert session["event_count"] == 2
        assert session["notebook_path"] == "test.ipynb"

        store.close()
