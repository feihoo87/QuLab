"""Tests for qulab.trace.server."""

import json

import pytest
from fastapi.testclient import TestClient

from qulab.trace.server import create_app


@pytest.fixture
def app_client(tmp_data_path):
    """Create a test client for the FastAPI app."""
    app = create_app(data_path=tmp_data_path)
    return TestClient(app)


class TestSubmitEvents:
    def test_submit_empty_batch(self, app_client):
        resp = app_client.post("/api/v1/events", json={"events": []})
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_submit_events(self, app_client):
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
                "payload": {"python_version": "3.12"},
            },
            {
                "event_id": "e2",
                "timestamp": "2026-04-16T10:00:01Z",
                "session_id": "s1",
                "kernel_id": "k1",
                "user_id": "user1",
                "notebook_path": "test.ipynb",
                "event_type": "cell_execute_start",
                "sequence_no": 2,
                "payload": {"code": "x = 1", "execution_count": 1},
            },
        ]
        resp = app_client.post("/api/v1/events", json={"events": events})
        assert resp.status_code == 200
        assert resp.json()["count"] == 2


class TestQuerySessions:
    def _seed_data(self, client):
        events = [
            {
                "event_id": f"e{i}",
                "timestamp": f"2026-04-16T{10+i}:00:00Z",
                "session_id": f"s{i}",
                "kernel_id": f"k{i}",
                "user_id": f"user{i % 2}",
                "notebook_path": f"nb{i}.ipynb",
                "event_type": "session_start",
                "sequence_no": 1,
                "payload": {},
            }
            for i in range(3)
        ]
        client.post("/api/v1/events", json={"events": events})

    def test_list_all_sessions(self, app_client):
        self._seed_data(app_client)
        resp = app_client.get("/api/v1/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    def test_filter_by_user(self, app_client):
        self._seed_data(app_client)
        resp = app_client.get("/api/v1/sessions", params={"user_id": "user0"})
        data = resp.json()
        assert data["total"] == 2  # i=0, i=2

    def test_pagination(self, app_client):
        self._seed_data(app_client)
        resp = app_client.get(
            "/api/v1/sessions", params={"limit": 2, "offset": 0}
        )
        data = resp.json()
        assert data["total"] == 3
        assert len(data["sessions"]) == 2


class TestQueryEvents:
    def test_get_session_events(self, app_client):
        events = [
            {
                "event_id": f"e{i}",
                "timestamp": f"2026-04-16T10:00:0{i}Z",
                "session_id": "s1",
                "kernel_id": "k1",
                "user_id": "",
                "notebook_path": "",
                "event_type": "cell_execute_start",
                "sequence_no": i,
                "payload": {"code": f"x={i}", "execution_count": i},
            }
            for i in range(3)
        ]
        app_client.post("/api/v1/events", json={"events": events})

        resp = app_client.get("/api/v1/sessions/s1/events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["events"]) == 3

    def test_filter_by_event_type(self, app_client):
        events = [
            {
                "event_id": "e1",
                "timestamp": "2026-04-16T10:00:00Z",
                "session_id": "s1",
                "kernel_id": "k1",
                "user_id": "",
                "notebook_path": "",
                "event_type": "cell_execute_start",
                "sequence_no": 1,
                "payload": {},
            },
            {
                "event_id": "e2",
                "timestamp": "2026-04-16T10:00:01Z",
                "session_id": "s1",
                "kernel_id": "k1",
                "user_id": "",
                "notebook_path": "",
                "event_type": "cell_execute_end",
                "sequence_no": 2,
                "payload": {},
            },
        ]
        app_client.post("/api/v1/events", json={"events": events})

        resp = app_client.get(
            "/api/v1/sessions/s1/events",
            params={"event_type": "cell_execute_start"},
        )
        data = resp.json()
        assert data["total"] == 1


class TestExport:
    def test_export_jsonl(self, app_client):
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
                "payload": {"code": f"x={i}", "execution_count": i},
            }
            for i in range(2)
        ]
        app_client.post("/api/v1/events", json={"events": events})

        resp = app_client.get("/api/v1/export")
        assert resp.status_code == 200
        lines = resp.text.strip().split("\n")
        assert len(lines) == 1  # One session
        trace = json.loads(lines[0])
        assert trace["session_id"] == "s1"
        assert len(trace["events"]) == 2


class TestStatus:
    def test_status_endpoint(self, app_client):
        resp = app_client.get("/api/v1/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "total_sessions" in data
        assert "total_events" in data
