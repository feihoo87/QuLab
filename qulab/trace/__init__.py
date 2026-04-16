"""QuLab Trace - Jupyter notebook behavior tracking for ML training.

Records user actions in Jupyter notebooks (code execution, outputs,
figure viewing, parameter modifications) and uploads the behavior
traces to a server for training automation models.

Quickstart in a notebook::

    import qulab.trace
    qulab.trace.enable()

To stop::

    qulab.trace.disable()
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from .client import TraceClient
from .hooks import setup_trace_hooks, teardown_trace_hooks
from .models import EventType, TraceEvent

__all__ = [
    "enable",
    "disable",
    "get_client",
    "TraceClient",
    "setup_trace_hooks",
    "teardown_trace_hooks",
    "EventType",
    "TraceEvent",
]

logger = logging.getLogger(__name__)

_client: Optional[TraceClient] = None  # pylint: disable=invalid-name
_watcher: object | None = None  # pylint: disable=invalid-name


def enable(
    server_url: Optional[str] = None,
    user_id: Optional[str] = None,
    local_only: bool = False,
    flush_interval: float = 30.0,
    flush_size: int = 200,
) -> TraceClient:
    """Enable trace recording in the current IPython/Jupyter session.

    Args:
        server_url: HTTP URL of the trace server.
            Defaults to ``QULAB_TRACE_URL`` env var or
            ``http://{QULAB_TRACE_HOST}:{QULAB_TRACE_PORT}``.
        user_id: Optional user identifier. Defaults to
            ``QULAB_TRACE_USER_ID`` env var.
        local_only: If True, only buffer locally without uploading.
        flush_interval: Seconds between automatic flushes.
        flush_size: Number of events before automatic flush.

    Returns:
        The active TraceClient instance.
    """
    global _client, _watcher  # pylint: disable=global-statement

    if _client is not None:
        return _client

    if server_url is None:
        server_url = _resolve_server_url()

    if user_id is None:
        user_id = os.environ.get("QULAB_TRACE_USER_ID")

    _client = TraceClient(
        server_url=server_url,
        user_id=user_id,
        local_only=local_only,
        flush_interval=flush_interval,
        flush_size=flush_size,
    )
    _client.start()

    # Detect notebook path once and set on client
    nb_path = TraceClient.detect_notebook_path()
    if nb_path:
        _client.notebook_path = nb_path

    # Emit session_start
    _emit_session_start(_client)

    # Register IPython hooks
    setup_trace_hooks(_client)

    # Start notebook file watcher for markdown/structure changes
    if nb_path:
        _watcher = _start_watcher(_client, nb_path)

    logger.info("Trace recording enabled (session=%s)", _client.session_id)
    return _client


def disable() -> None:
    """Disable trace recording and flush remaining events."""
    global _client, _watcher  # pylint: disable=global-statement

    if _client is None:
        return

    # Emit session_end
    _client.emit(
        EventType.SESSION_END,
        {"reason": "normal", "total_executions": _client.total_events},
    )

    # Stop watcher
    if _watcher is not None:
        try:
            _watcher.stop()  # type: ignore[union-attr]
        except Exception:  # pylint: disable=broad-except
            pass
        _watcher = None

    teardown_trace_hooks()
    _client.stop()
    logger.info("Trace recording disabled (session=%s)", _client.session_id)
    _client = None


def get_client() -> Optional[TraceClient]:
    """Get the active TraceClient, or None if tracing is disabled."""
    return _client


def _resolve_server_url() -> str:
    """Resolve the server URL from environment variables."""
    url = os.environ.get("QULAB_TRACE_URL")
    if url:
        return url
    host = os.environ.get("QULAB_TRACE_HOST", "127.0.0.1")
    port = os.environ.get("QULAB_TRACE_PORT", "8790")
    return f"http://{host}:{port}"


def _emit_session_start(client: TraceClient) -> None:
    """Emit a session_start event with environment info."""
    import platform
    import sys

    payload: dict = {
        "python_version": sys.version,
        "hostname": platform.node(),
        "notebook_path": client.notebook_path or "",
        "kernel_info": {},
    }

    try:
        import IPython

        payload["ipython_version"] = IPython.__version__
    except ImportError:
        payload["ipython_version"] = ""

    try:
        from qulab.version import __version__

        payload["qulab_version"] = __version__
    except ImportError:
        payload["qulab_version"] = ""

    client.emit(EventType.SESSION_START, payload)


def _start_watcher(client: TraceClient, notebook_path: str) -> object | None:
    """Start the notebook file watcher if possible."""
    try:
        from .watcher import NotebookWatcher

        watcher = NotebookWatcher(client, notebook_path)
        watcher.start()
        return watcher
    except Exception:  # pylint: disable=broad-except
        logger.debug("Failed to start notebook watcher", exc_info=True)
        return None
