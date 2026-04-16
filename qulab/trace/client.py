"""TraceClient: local JSONL buffering and HTTP batch upload.

Handles event emission, local crash-safe buffering to JSONL files,
and background-thread HTTP upload to the trace server.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
import uuid
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from .models import EventType, TraceEvent

logger = logging.getLogger(__name__)

_DEFAULT_BUFFER_DIR = Path.home() / ".qulab" / "trace" / "buffer"


class TraceClient:
    """Client that buffers trace events locally and uploads to a server.

    Events are appended to a local JSONL file for crash safety,
    and periodically uploaded in batches via HTTP POST.
    """

    def __init__(
        self,
        server_url: str = "http://127.0.0.1:8790",
        buffer_dir: Optional[Path] = None,
        flush_interval: float = 30.0,
        flush_size: int = 200,
        enabled: bool = True,
        user_id: Optional[str] = None,
        local_only: bool = False,
    ):
        self.server_url = server_url.rstrip("/")
        self.buffer_dir = buffer_dir or _DEFAULT_BUFFER_DIR
        self.flush_interval = flush_interval
        self.flush_size = flush_size
        self.enabled = enabled
        self.user_id = user_id
        self.local_only = local_only

        self.session_id = uuid.uuid4().hex
        self.kernel_id = self._detect_kernel_id()
        self.notebook_path: Optional[str] = None

        self._sequence_no = 0
        self._cell_code_history: dict[str, str] = {}  # diff_key -> code_hash
        self._cell_code_by_hash: dict[str, str] = {}  # code_hash -> code
        self._exec_history: list[tuple[str, str]] = []  # [(code_hash, code)]
        self._queue: queue.Queue[TraceEvent | None] = queue.Queue()
        self._buffer: list[dict] = []
        self._last_flush_time = time.monotonic()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._buffer_file: Optional[Path] = None
        self._lock = threading.Lock()

    @property
    def total_events(self) -> int:
        """Total number of events emitted in this session."""
        return self._sequence_no

    # --- Public API ---

    def start(self) -> None:
        """Start the background upload thread and emit session_start."""
        if self._running:
            return
        self._running = True
        self.buffer_dir.mkdir(parents=True, exist_ok=True)
        self._buffer_file = self.buffer_dir / f"{self.session_id}.jsonl"
        self._thread = threading.Thread(
            target=self._upload_loop, daemon=True, name="trace-upload"
        )
        self._thread.start()

    def stop(self) -> None:
        """Flush remaining events and stop the upload thread."""
        if not self._running:
            return
        self._running = False
        self._queue.put(None)  # Sentinel to wake up the thread
        if self._thread is not None:
            self._thread.join(timeout=10)
        self._flush_buffer()

    def emit(self, event_type: EventType, payload: dict) -> None:
        """Emit a trace event.

        Args:
            event_type: The type of event.
            payload: Event-specific payload dict.
        """
        if not self.enabled:
            return

        self._sequence_no += 1
        event = TraceEvent(
            session_id=self.session_id,
            kernel_id=self.kernel_id,
            notebook_path=self.notebook_path or self.detect_notebook_path(),
            user_id=self.user_id,
            event_type=event_type,
            sequence_no=self._sequence_no,
            payload=payload,
        )

        # Write to local JSONL file for crash safety
        self._append_to_file(event)

        # Queue for batch upload
        if not self.local_only:
            self._queue.put(event)

    def flush(self) -> None:
        """Force flush the current buffer to the server."""
        self._flush_buffer()

    def get_cell_code_hash(self, diff_key: str) -> Optional[str]:
        """Get the code hash from the last execution of a cell.

        Args:
            diff_key: Cell identifier (cell_id or str(execution_count)).
        """
        return self._cell_code_history.get(diff_key)

    def get_cell_code(self, code_hash: str) -> Optional[str]:
        """Get the source code for a given code hash."""
        return self._cell_code_by_hash.get(code_hash)

    def record_cell_code(
        self, diff_key: str, code_hash: str, code: str
    ) -> None:
        """Record the code hash and source for a cell execution.

        Args:
            diff_key: Cell identifier (cell_id or str(execution_count)).
            code_hash: SHA256 hex digest of the code.
            code: The full source code.
        """
        self._cell_code_history[diff_key] = code_hash
        self._cell_code_by_hash[code_hash] = code
        self._exec_history.append((code_hash, code))

    def find_most_similar_code(
        self, code: str, code_hash: str, threshold: float = 0.5
    ) -> Optional[str]:
        """Find the most recent previously executed code similar to *code*.

        Used as a fallback when cell_id is unavailable for diff computation.
        Walks the execution history backward and returns the first code
        with line-level similarity above *threshold*.

        Returns:
            Previous code string, or None if no match found.
        """
        if not self._exec_history:
            return None

        code_lines = set(code.splitlines())
        if not code_lines:
            return None

        # Walk history backward, skip exact same code
        for prev_hash, prev_code in reversed(self._exec_history):
            if prev_hash == code_hash:
                continue
            prev_lines = set(prev_code.splitlines())
            if not prev_lines:
                continue
            overlap = len(code_lines & prev_lines)
            total = max(len(code_lines), len(prev_lines))
            if overlap / total >= threshold:
                return prev_code

        return None

    # --- Internal ---

    def _append_to_file(self, event: TraceEvent) -> None:
        """Append an event to the local JSONL buffer file."""
        if self._buffer_file is None:
            return
        try:
            line = json.dumps(event.to_jsonl_dict(), ensure_ascii=False)
            with open(self._buffer_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:  # pylint: disable=broad-except
            logger.debug("Failed to write event to buffer file", exc_info=True)

    def _upload_loop(self) -> None:
        """Background thread: collect events from queue and upload."""
        while self._running:
            try:
                event = self._queue.get(timeout=1.0)
            except queue.Empty:
                # Check if it's time for a periodic flush
                if self._should_flush():
                    self._flush_buffer()
                continue

            if event is None:
                # Sentinel: stop signal
                break

            with self._lock:
                self._buffer.append(event.to_jsonl_dict())

            if self._should_flush():
                self._flush_buffer()

        # Final flush on shutdown
        self._flush_buffer()

    def _should_flush(self) -> bool:
        """Check if the buffer should be flushed."""
        with self._lock:
            if not self._buffer:
                return False
            if len(self._buffer) >= self.flush_size:
                return True
        elapsed = time.monotonic() - self._last_flush_time
        return elapsed >= self.flush_interval

    def _flush_buffer(self) -> None:
        """Send buffered events to the server via HTTP POST."""
        with self._lock:
            if not self._buffer:
                return
            batch = self._buffer[:]
            self._buffer.clear()

        self._last_flush_time = time.monotonic()

        if self.local_only:
            return

        try:
            url = f"{self.server_url}/api/v1/events"
            body = json.dumps({"events": batch}).encode("utf-8")
            req = Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=10) as resp:
                resp.read()
            self._update_upload_meta(len(batch))
        except (URLError, OSError) as exc:
            logger.debug("Failed to upload events: %s", exc)
            # Put events back for retry
            with self._lock:
                self._buffer = batch + self._buffer
        except Exception:  # pylint: disable=broad-except
            logger.debug("Unexpected error uploading events", exc_info=True)
            with self._lock:
                self._buffer = batch + self._buffer

    def _update_upload_meta(self, count: int) -> None:
        """Update the .meta file with the last uploaded line count."""
        if self._buffer_file is None:
            return
        meta_file = self._buffer_file.with_suffix(".meta")
        try:
            existing = 0
            if meta_file.exists():
                existing = int(meta_file.read_text(encoding="utf-8").strip())
            meta_file.write_text(
                str(existing + count), encoding="utf-8"
            )
        except Exception:  # pylint: disable=broad-except
            pass

    @staticmethod
    def _detect_kernel_id() -> str:
        """Detect the IPython kernel ID if running in a notebook."""
        try:
            from IPython import get_ipython

            ip = get_ipython()
            if ip is not None and hasattr(ip, "kernel"):
                return ip.kernel.session.session
        except Exception:  # pylint: disable=broad-except
            pass

        return f"unknown-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def detect_notebook_path() -> Optional[str]:
        """Try to detect the current notebook file path.

        Tries multiple methods in order:
        1. ``JPY_SESSION_NAME`` env var (Jupyter Server 2+ / JupyterLab 3+)
        2. ``__session__`` in user namespace (ipykernel)
        3. Kernel connection file + Notebook server API (classic Notebook 5.x)
        """
        nb_path = os.environ.get("JPY_SESSION_NAME")
        if nb_path:
            return nb_path

        try:
            from IPython import get_ipython

            ip = get_ipython()
            if ip is not None:
                session_name = ip.user_ns.get("__session__")
                if session_name:
                    return str(session_name)
        except Exception:  # pylint: disable=broad-except
            pass

        # Fallback: kernel connection file + notebook server API
        return _detect_notebook_path_via_server()


def _detect_notebook_path_via_server() -> Optional[str]:
    """Detect notebook path via kernel connection file + server sessions API.

    Works with classic Notebook 5.x and Jupyter Server.
    """
    kernel_id = _get_kernel_id_from_connection()
    if kernel_id is None:
        return None
    return _query_notebook_path(kernel_id)


def _get_kernel_id_from_connection() -> Optional[str]:
    """Extract the kernel ID from the ipykernel connection file."""
    try:
        import re

        import ipykernel.connect  # pylint: disable=import-error

        connection_file = ipykernel.connect.get_connection_file()
        match = re.search(r"kernel-(.+)\.json", connection_file)
        return match.group(1) if match else None
    except Exception:  # pylint: disable=broad-except
        return None


def _query_notebook_path(kernel_id: str) -> Optional[str]:
    """Query running Jupyter servers to find the notebook for a kernel."""
    servers: list = []
    try:
        from notebook.notebookapp import list_running_servers
        servers = list(list_running_servers())
    except ImportError:
        pass
    if not servers:
        try:
            from jupyter_server.serverapp import list_running_servers
            servers = list(list_running_servers())
        except ImportError:
            pass

    for srv in servers:
        nb_path = _match_kernel_in_server(srv, kernel_id)
        if nb_path:
            return nb_path
    return None


def _match_kernel_in_server(srv: dict, kernel_id: str) -> Optional[str]:
    """Check one Jupyter server for a matching kernel session."""
    url = srv.get("url", "").rstrip("/")
    token = srv.get("token", "")
    try:
        api_url = f"{url}/api/sessions?token={token}"
        req = Request(api_url, method="GET")
        with urlopen(req, timeout=2) as resp:
            sessions = json.loads(resp.read().decode("utf-8"))
        for sess in sessions:
            if sess.get("kernel", {}).get("id") == kernel_id:
                nb = sess.get("notebook", {}).get("path", "")
                if not nb:
                    nb = sess.get("path", "")
                if nb:
                    return nb
    except Exception:  # pylint: disable=broad-except
        pass
    return None


def upload_buffer_files(
    buffer_dir: Path,
    server_url: str,
    batch_size: int = 500,
) -> dict[str, int]:
    """Upload local buffer files that were not fully uploaded.

    Used by the CLI ``upload-buffer`` command to retroactively upload
    events from sessions where the server was unreachable.

    Args:
        buffer_dir: Directory containing .jsonl buffer files.
        server_url: Server base URL.
        batch_size: Number of events per upload batch.

    Returns:
        Dict mapping filename to number of events uploaded.
    """
    results: dict[str, int] = {}
    server_url = server_url.rstrip("/")

    for jsonl_file in sorted(buffer_dir.glob("*.jsonl")):
        meta_file = jsonl_file.with_suffix(".meta")
        uploaded_lines = 0
        if meta_file.exists():
            try:
                uploaded_lines = int(
                    meta_file.read_text(encoding="utf-8").strip()
                )
            except ValueError:
                uploaded_lines = 0

        # Read remaining lines
        with open(jsonl_file, encoding="utf-8") as f:
            all_lines = f.readlines()

        remaining = all_lines[uploaded_lines:]
        if not remaining:
            continue

        count = 0
        for i in range(0, len(remaining), batch_size):
            batch_lines = remaining[i : i + batch_size]
            events = []
            for line in batch_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

            if not events:
                continue

            try:
                url = f"{server_url}/api/v1/events"
                body = json.dumps({"events": events}).encode("utf-8")
                req = Request(
                    url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(req, timeout=30) as resp:
                    resp.read()
                count += len(events)
            except (URLError, OSError) as exc:
                logger.warning(
                    "Failed to upload batch from %s: %s", jsonl_file.name, exc
                )
                break

        if count > 0:
            meta_file.write_text(
                str(uploaded_lines + count), encoding="utf-8"
            )
            results[jsonl_file.name] = count

    return results
