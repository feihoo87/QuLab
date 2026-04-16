"""Server-side storage for the trace system.

Dual storage: JSONL files for ML-friendly sequential access,
SQLite for indexed queries over sessions and events.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS trace_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    kernel_id TEXT NOT NULL DEFAULT '',
    user_id TEXT DEFAULT '',
    notebook_path TEXT DEFAULT '',
    start_time TEXT,
    end_time TEXT,
    event_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_sessions_user
    ON trace_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_start
    ON trace_sessions(start_time);

CREATE TABLE IF NOT EXISTS trace_event_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    execution_count INTEGER,
    jsonl_file TEXT NOT NULL,
    line_offset INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_session
    ON trace_event_index(session_id);
CREATE INDEX IF NOT EXISTS idx_events_type
    ON trace_event_index(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp
    ON trace_event_index(timestamp);
"""


class TraceStore:
    """Manages JSONL event files and a SQLite index for queries."""

    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.events_dir = data_path / "events"
        self.events_dir.mkdir(parents=True, exist_ok=True)

        self._db_path = data_path / "trace.db"
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database with schema."""
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def write_events(self, events: list[dict]) -> int:
        """Write a batch of events to JSONL and update SQLite index.

        Args:
            events: List of event dicts (already validated).

        Returns:
            Number of events written.
        """
        if not events:
            return 0

        count = 0
        for event in events:
            ts = event.get("timestamp", "")
            date_str = ts[:10] if len(ts) >= 10 else "unknown"
            jsonl_file = f"{date_str}.jsonl"
            file_path = self.events_dir / jsonl_file

            # Append to JSONL
            line = json.dumps(event, ensure_ascii=False)
            with open(file_path, "a", encoding="utf-8") as f:
                line_offset = f.tell()
                f.write(line + "\n")

            # Update SQLite index
            self._index_event(event, jsonl_file, line_offset)
            count += 1

        # Update session metadata
        self._update_sessions(events)
        self._conn.commit()
        return count

    def _index_event(
        self, event: dict, jsonl_file: str, line_offset: int
    ) -> None:
        """Insert an event into the SQLite index."""
        payload = event.get("payload", {})
        self._conn.execute(
            """INSERT INTO trace_event_index
               (session_id, event_type, timestamp, execution_count,
                jsonl_file, line_offset)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                event.get("session_id", ""),
                event.get("event_type", ""),
                event.get("timestamp", ""),
                payload.get("execution_count"),
                jsonl_file,
                line_offset,
            ),
        )

    def _update_sessions(self, events: list[dict]) -> None:
        """Update session metadata from a batch of events."""
        sessions: dict[str, dict] = {}
        for event in events:
            sid = event.get("session_id", "")
            if sid not in sessions:
                sessions[sid] = {
                    "session_id": sid,
                    "kernel_id": event.get("kernel_id", ""),
                    "user_id": event.get("user_id", ""),
                    "notebook_path": event.get("notebook_path", ""),
                    "timestamps": [],
                    "count": 0,
                }
            sessions[sid]["timestamps"].append(event.get("timestamp", ""))
            sessions[sid]["count"] += 1

            # Update notebook_path if we get a non-empty one
            nb = event.get("notebook_path")
            if nb:
                sessions[sid]["notebook_path"] = nb

        for sid, info in sessions.items():
            timestamps = sorted(info["timestamps"])
            row = self._conn.execute(
                "SELECT id, event_count FROM trace_sessions WHERE session_id = ?",
                (sid,),
            ).fetchone()

            if row is None:
                self._conn.execute(
                    """INSERT INTO trace_sessions
                       (session_id, kernel_id, user_id, notebook_path,
                        start_time, end_time, event_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        sid,
                        info["kernel_id"],
                        info["user_id"],
                        info["notebook_path"],
                        timestamps[0] if timestamps else None,
                        timestamps[-1] if timestamps else None,
                        info["count"],
                    ),
                )
            else:
                self._conn.execute(
                    """UPDATE trace_sessions
                       SET end_time = ?,
                           event_count = event_count + ?,
                           notebook_path = CASE
                               WHEN ? != '' THEN ?
                               ELSE notebook_path
                           END
                       WHERE session_id = ?""",
                    (
                        timestamps[-1] if timestamps else None,
                        info["count"],
                        info["notebook_path"],
                        info["notebook_path"],
                        sid,
                    ),
                )

    def query_sessions(
        self,
        user_id: Optional[str] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> dict:
        """Query session metadata.

        Returns:
            Dict with 'total' count and 'sessions' list.
        """
        conditions = []
        params: list = []

        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if after:
            conditions.append("start_time >= ?")
            params.append(after)
        if before:
            conditions.append("start_time <= ?")
            params.append(before)

        where = " AND ".join(conditions) if conditions else "1=1"

        total = self._conn.execute(
            f"SELECT COUNT(*) FROM trace_sessions WHERE {where}", params
        ).fetchone()[0]

        rows = self._conn.execute(
            f"""SELECT session_id, kernel_id, user_id, notebook_path,
                       start_time, end_time, event_count
                FROM trace_sessions
                WHERE {where}
                ORDER BY start_time DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ).fetchall()

        return {
            "total": total,
            "sessions": [dict(row) for row in rows],
        }

    def query_events(
        self,
        session_id: Optional[str] = None,
        event_type: Optional[str] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        offset: int = 0,
        limit: int = 1000,
    ) -> dict:
        """Query events by reading from JSONL files using the index.

        Returns:
            Dict with 'total' count and 'events' list.
        """
        conditions = []
        params: list = []

        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if after:
            conditions.append("timestamp >= ?")
            params.append(after)
        if before:
            conditions.append("timestamp <= ?")
            params.append(before)

        where = " AND ".join(conditions) if conditions else "1=1"

        total = self._conn.execute(
            f"SELECT COUNT(*) FROM trace_event_index WHERE {where}", params
        ).fetchone()[0]

        rows = self._conn.execute(
            f"""SELECT jsonl_file, line_offset
                FROM trace_event_index
                WHERE {where}
                ORDER BY timestamp ASC
                LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ).fetchall()

        events = []
        for row in rows:
            event = self._read_event(row["jsonl_file"], row["line_offset"])
            if event is not None:
                events.append(event)

        return {"total": total, "events": events}

    def _read_event(self, jsonl_file: str, line_offset: int) -> Optional[dict]:
        """Read a single event from a JSONL file at the given offset."""
        file_path = self.events_dir / jsonl_file
        if not file_path.exists():
            return None
        try:
            with open(file_path, encoding="utf-8") as f:
                f.seek(line_offset)
                line = f.readline()
                return json.loads(line) if line else None
        except (json.JSONDecodeError, OSError):
            return None

    def export_training_data(
        self,
        session_ids: Optional[list[str]] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
    ) -> list[dict]:
        """Export session traces formatted for ML training.

        Each returned dict is a complete session with all events
        in chronological order.

        Returns:
            List of session trace dicts.
        """
        # Get matching sessions
        conditions = []
        params: list = []

        if session_ids:
            placeholders = ",".join("?" for _ in session_ids)
            conditions.append(f"session_id IN ({placeholders})")
            params.extend(session_ids)
        if after:
            conditions.append("start_time >= ?")
            params.append(after)
        if before:
            conditions.append("start_time <= ?")
            params.append(before)

        where = " AND ".join(conditions) if conditions else "1=1"

        sessions = self._conn.execute(
            f"""SELECT session_id, kernel_id, user_id, notebook_path,
                       start_time, end_time
                FROM trace_sessions
                WHERE {where}
                ORDER BY start_time ASC""",
            params,
        ).fetchall()

        results = []
        for session in sessions:
            sid = session["session_id"]
            events_result = self.query_events(session_id=sid, limit=100_000)
            results.append({
                "session_id": sid,
                "kernel_id": session["kernel_id"],
                "user_id": session["user_id"],
                "notebook_path": session["notebook_path"],
                "start_time": session["start_time"],
                "end_time": session["end_time"],
                "events": events_result["events"],
            })

        return results

    def get_stats(self) -> dict:
        """Get storage statistics."""
        total_sessions = self._conn.execute(
            "SELECT COUNT(*) FROM trace_sessions"
        ).fetchone()[0]
        total_events = self._conn.execute(
            "SELECT COUNT(*) FROM trace_event_index"
        ).fetchone()[0]

        # Count JSONL files and total size
        jsonl_files = list(self.events_dir.glob("*.jsonl"))
        total_size = sum(f.stat().st_size for f in jsonl_files)

        return {
            "total_sessions": total_sessions,
            "total_events": total_events,
            "jsonl_files": len(jsonl_files),
            "total_size_bytes": total_size,
            "data_path": str(self.data_path),
        }
