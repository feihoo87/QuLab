"""FastAPI server for the trace system.

Receives trace events from notebook clients, stores them,
and provides query/export APIs for training data extraction.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .storage import TraceStore

logger = logging.getLogger(__name__)


# --- Request/Response models ---


class EventBatchRequest(BaseModel):
    """Request body for submitting events."""

    events: list[dict]


class EventBatchResponse(BaseModel):
    """Response for event submission."""

    status: str = "ok"
    count: int = 0


class StatusResponse(BaseModel):
    """Server status response."""

    status: str = "ok"
    total_sessions: int = 0
    total_events: int = 0
    jsonl_files: int = 0
    total_size_bytes: int = 0
    data_path: str = ""


# --- App factory ---


def create_app(data_path: Optional[Path] = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        data_path: Directory for storing trace data.
            Defaults to ``~/.qulab/trace/data``.

    Returns:
        Configured FastAPI app.
    """
    if data_path is None:
        data_path = Path.home() / ".qulab" / "trace" / "data"

    store = TraceStore(data_path)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):  # pylint: disable=unused-argument
        yield
        store.close()

    app = FastAPI(
        title="QuLab Trace Server",
        description="Jupyter notebook behavior tracking for ML training",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.post("/api/v1/events", response_model=EventBatchResponse)
    async def submit_events(batch: EventBatchRequest) -> EventBatchResponse:
        """Receive a batch of trace events."""
        count = store.write_events(batch.events)
        return EventBatchResponse(count=count)

    @app.get("/api/v1/sessions")
    async def list_sessions(
        user_id: Optional[str] = Query(None),
        after: Optional[str] = Query(None),
        before: Optional[str] = Query(None),
        offset: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
    ) -> dict:
        """Query session metadata."""
        return store.query_sessions(
            user_id=user_id,
            after=after,
            before=before,
            offset=offset,
            limit=limit,
        )

    @app.get("/api/v1/sessions/{session_id}/events")
    async def get_session_events(
        session_id: str,
        event_type: Optional[str] = Query(None),
        offset: int = Query(0, ge=0),
        limit: int = Query(1000, ge=1, le=10000),
    ) -> dict:
        """Get events for a specific session."""
        return store.query_events(
            session_id=session_id,
            event_type=event_type,
            offset=offset,
            limit=limit,
        )

    @app.get("/api/v1/export")
    async def export_training_data(
        session_id: Optional[str] = Query(None),
        after: Optional[str] = Query(None),
        before: Optional[str] = Query(None),
    ) -> StreamingResponse:
        """Export training data as streaming JSONL.

        Each line is a complete session trace with all events.
        """
        session_ids = [session_id] if session_id else None
        traces = store.export_training_data(
            session_ids=session_ids, after=after, before=before
        )

        def generate():
            for trace in traces:
                yield json.dumps(trace, ensure_ascii=False) + "\n"

        return StreamingResponse(
            generate(),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": "attachment; filename=traces.jsonl"},
        )

    @app.get("/api/v1/status", response_model=StatusResponse)
    async def server_status() -> StatusResponse:
        """Get server status and storage statistics."""
        stats = store.get_stats()
        return StatusResponse(
            total_sessions=stats["total_sessions"],
            total_events=stats["total_events"],
            jsonl_files=stats["jsonl_files"],
            total_size_bytes=stats["total_size_bytes"],
            data_path=stats["data_path"],
        )

    return app
