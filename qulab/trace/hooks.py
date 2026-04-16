"""IPython event hooks for the trace system.

Registers pre_run_cell and post_run_cell callbacks to capture
cell execution events, display outputs (including inline figures),
and code modifications with diffs keyed by cell_id.
"""

from __future__ import annotations

import difflib
import hashlib
import logging
import time
from typing import Any, Optional

from .capture import (
    DisplayCapture,
    StreamCapture,
    extract_cell_error,
    extract_cell_outputs,
    extract_display_data,
)
from .client import TraceClient
from .models import EventType

logger = logging.getLogger(__name__)

# Module-level state for the active cell execution
_display_capture: Optional[DisplayCapture] = None
_stream_capture: Optional[StreamCapture] = None
_cell_start_time: float = 0.0
_current_cell_id: str = ""

# References to registered callbacks for teardown
_pre_run_cb: Any = None
_post_run_cb: Any = None


def setup_trace_hooks(client: TraceClient) -> None:
    """Register IPython event hooks for trace capture.

    Args:
        client: The TraceClient instance to emit events to.
    """
    global _pre_run_cb, _post_run_cb  # pylint: disable=global-statement

    try:
        from IPython import get_ipython
    except ImportError:
        logger.debug("IPython not available, skipping trace hook setup")
        return

    ip = get_ipython()
    if ip is None:
        logger.debug("No active IPython instance, skipping trace hook setup")
        return

    def pre_run(info: Any) -> None:
        _on_pre_run(client, info)

    def post_run(result: Any) -> None:
        _on_post_run(client, result)

    _pre_run_cb = pre_run
    _post_run_cb = post_run

    ip.events.register("pre_run_cell", pre_run)
    ip.events.register("post_run_cell", post_run)
    logger.debug("Trace hooks registered successfully")


def teardown_trace_hooks() -> None:
    """Unregister IPython event hooks."""
    global _pre_run_cb, _post_run_cb  # pylint: disable=global-statement

    try:
        from IPython import get_ipython
    except ImportError:
        return

    ip = get_ipython()
    if ip is None:
        return

    if _pre_run_cb is not None:
        try:
            ip.events.unregister("pre_run_cell", _pre_run_cb)
        except ValueError:
            pass
        _pre_run_cb = None

    if _post_run_cb is not None:
        try:
            ip.events.unregister("post_run_cell", _post_run_cb)
        except ValueError:
            pass
        _post_run_cb = None

    logger.debug("Trace hooks unregistered")


def _on_pre_run(client: TraceClient, info: Any) -> None:
    """Handle pre_run_cell event.

    Captures the cell source code, cell_id, computes diff against
    previous execution of the same cell, installs display capture,
    and emits CELL_EXECUTE_START.
    """
    # pylint: disable=global-statement
    global _display_capture, _stream_capture, _cell_start_time, _current_cell_id

    try:
        code = info.raw_cell
        if not code or not code.strip():
            return

        # Get cell_id from Jupyter (protocol 5.5+ / nbformat 4.5+)
        cell_id = getattr(info, "cell_id", None) or ""
        _current_cell_id = cell_id

        # Determine execution_count
        try:
            from IPython import get_ipython

            ip = get_ipython()
            execution_count = ip.execution_count if ip else 0
        except Exception:  # pylint: disable=broad-except
            execution_count = 0

        code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()

        # Compute diff using cell_id as key (falls back to execution_count)
        diff_key = cell_id if cell_id else str(execution_count)
        diff_ops = _compute_diff(client, diff_key, code, code_hash)

        # Record this code hash and source
        client.record_cell_code(diff_key, code_hash, code)

        client.emit(
            EventType.CELL_EXECUTE_START,
            {
                "cell_id": cell_id,
                "execution_count": execution_count,
                "code": code,
                "code_hash": code_hash,
                "diff_ops": diff_ops,
            },
        )

        # Install display capture to intercept inline figures
        _display_capture = DisplayCapture()
        _display_capture.install()

        # Start capturing stdout/stderr
        _stream_capture = StreamCapture()
        _stream_capture.__enter__()  # pylint: disable=unnecessary-dunder-call
        _cell_start_time = time.monotonic()

    except Exception:  # pylint: disable=broad-except
        logger.debug("Error in pre_run_cell hook", exc_info=True)


def _on_post_run(client: TraceClient, result: Any) -> None:
    """Handle post_run_cell event.

    Uninstalls display capture, captures execution result, outputs,
    errors, and display data (including figures).
    Emits CELL_EXECUTE_END + CELL_OUTPUT / CELL_ERROR / DISPLAY_DATA.
    """
    # pylint: disable=global-statement,global-variable-not-assigned
    global _display_capture, _stream_capture, _cell_start_time, _current_cell_id

    try:
        execution_count = getattr(result, "execution_count", 0) or 0
        duration_ms = (time.monotonic() - _cell_start_time) * 1000

        # Get cell_id from result (same as info.cell_id)
        cell_id = _current_cell_id
        if not cell_id:
            res_info = getattr(result, "info", None)
            if res_info is not None:
                cell_id = getattr(res_info, "cell_id", None) or ""

        # Uninstall display capture — get all display_data outputs
        display_outputs: list[dict] = []
        if _display_capture is not None:
            display_outputs = _display_capture.uninstall()
            _display_capture = None

        # Stop stream capture
        stdout_text = ""
        stderr_text = ""
        stdout_truncated = False
        stderr_truncated = False
        if _stream_capture is not None:
            _stream_capture.__exit__(None, None, None)  # pylint: disable=unnecessary-dunder-call
            stdout_text = _stream_capture.stdout_text
            stderr_text = _stream_capture.stderr_text
            stdout_truncated = _stream_capture.stdout_truncated
            stderr_truncated = _stream_capture.stderr_truncated
            _stream_capture = None

        has_error = bool(
            getattr(result, "error_in_exec", None)
            or getattr(result, "error_before_exec", None)
        )
        success = not has_error

        # Collect output MIME types
        mime_types: list[str] = []
        if result.result is not None:
            mime_types.append("text/plain")
        if has_error:
            mime_types.append("application/vnd.error")
        for output in display_outputs:
            for mt in output.get("data", {}):
                if mt not in mime_types:
                    mime_types.append(mt)

        has_display = bool(display_outputs)

        # Emit CELL_EXECUTE_END
        client.emit(
            EventType.CELL_EXECUTE_END,
            {
                "cell_id": cell_id,
                "execution_count": execution_count,
                "duration_ms": round(duration_ms, 2),
                "success": success,
                "output_mime_types": mime_types,
                "has_display_data": has_display,
            },
        )

        # Emit CELL_OUTPUT for stdout
        if stdout_text:
            client.emit(
                EventType.CELL_OUTPUT,
                {
                    "cell_id": cell_id,
                    "execution_count": execution_count,
                    "mime_type": "text/plain",
                    "content": stdout_text,
                    "stream": "stdout",
                    "truncated": stdout_truncated,
                },
            )

        # Emit CELL_OUTPUT for stderr
        if stderr_text:
            client.emit(
                EventType.CELL_OUTPUT,
                {
                    "cell_id": cell_id,
                    "execution_count": execution_count,
                    "mime_type": "text/plain",
                    "content": stderr_text,
                    "stream": "stderr",
                    "truncated": stderr_truncated,
                },
            )

        # Emit CELL_OUTPUT for display outputs (return value repr)
        for output in extract_cell_outputs(result, cell_id=cell_id):
            client.emit(EventType.CELL_OUTPUT, output)

        # Emit CELL_ERROR
        if has_error:
            error_data = extract_cell_error(result, cell_id=cell_id)
            if error_data:
                client.emit(EventType.CELL_ERROR, error_data)

        # Emit DISPLAY_DATA for each captured display output
        for dd_payload in extract_display_data(
            display_outputs, execution_count, cell_id=cell_id
        ):
            client.emit(EventType.DISPLAY_DATA, dd_payload)

    except Exception:  # pylint: disable=broad-except
        logger.debug("Error in post_run_cell hook", exc_info=True)


def _compute_diff(
    client: TraceClient,
    diff_key: str,
    code: str,
    code_hash: str,
) -> list[dict]:
    """Compute diff between current code and previous execution of the same cell.

    When ``cell_id`` is available, diffs are keyed by it directly.
    When ``cell_id`` is empty (classic Notebook 5.x), falls back to
    finding the most similar recently executed code via line overlap.

    Returns:
        List of diff operation dicts. Empty if no previous version or
        code is unchanged.
    """
    prev_code = None

    # Method 1: exact key lookup (works when cell_id is available)
    prev_hash = client.get_cell_code_hash(diff_key)
    if prev_hash is not None and prev_hash != code_hash:
        prev_code = client.get_cell_code(prev_hash)

    # Method 2: similarity-based fallback (when cell_id is empty)
    if prev_code is None:
        prev_code = client.find_most_similar_code(code, code_hash)

    if prev_code is None:
        return []

    return _unified_diff_ops(prev_code, code)


def _unified_diff_ops(old_code: str, new_code: str) -> list[dict]:
    """Produce diff ops from two code strings."""
    old_lines = old_code.splitlines(keepends=True)
    new_lines = new_code.splitlines(keepends=True)

    diff_ops = []
    for line in difflib.unified_diff(old_lines, new_lines, lineterm=""):
        if line.startswith("@@") or line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            diff_ops.append({"op": "delete", "line": line[1:]})
        elif line.startswith("+"):
            diff_ops.append({"op": "insert", "line": line[1:]})

    return diff_ops
