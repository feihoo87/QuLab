"""Output capture utilities for the trace system.

Captures display outputs (figures, HTML, rich objects) via IPython's
display publisher, stdout/stderr streams, and error information.
"""

from __future__ import annotations

import base64
import io
import sys
from typing import Any


# --- Display output capture via IPython's display publisher ---


class DisplayCapture:
    """Captures IPython display outputs by swapping the display publisher.

    The inline matplotlib backend calls ``plt.close('all')`` in the
    ``post_execute`` event, which fires *before* ``post_run_cell``.
    By that time ``plt.get_fignums()`` is empty. This class intercepts
    display data at the publisher level, before figures are closed.

    Usage::

        cap = DisplayCapture()
        cap.install()   # call in pre_run_cell
        # ... cell executes, inline backend flushes figures ...
        outputs = cap.uninstall()  # call in post_run_cell
    """

    def __init__(self) -> None:
        self._original_pub: Any = None
        self._outputs: list[dict] = []
        self._installed = False

    def install(self) -> None:
        """Replace IPython's display publisher with a capturing wrapper."""
        try:
            from IPython import get_ipython
        except ImportError:
            return

        ip = get_ipython()
        if ip is None:
            return

        self._original_pub = ip.display_pub
        self._outputs = []
        self._installed = True

        # Create a wrapper that captures and forwards
        wrapper = _DisplayPubWrapper(self._original_pub, self._outputs)
        ip.display_pub = wrapper

    def uninstall(self) -> list[dict]:
        """Restore the original display publisher and return captured outputs.

        Returns:
            List of display data dicts. Each has ``"data"`` (mime bundle)
            and ``"metadata"`` keys matching IPython's display_data format.
        """
        if not self._installed:
            return []

        try:
            from IPython import get_ipython
        except ImportError:
            return []

        ip = get_ipython()
        if ip is not None and self._original_pub is not None:
            ip.display_pub = self._original_pub

        self._installed = False
        return self._outputs


class _DisplayPubWrapper:
    """Wraps IPython's display publisher to capture outputs."""

    def __init__(self, original: Any, outputs: list[dict]):
        self._original = original
        self._outputs = outputs

    def publish(self, data: dict, metadata: Any = None,
                **kwargs: Any) -> None:
        """Capture display data then forward to the original publisher."""
        self._outputs.append({
            "data": dict(data) if data else {},
            "metadata": dict(metadata) if metadata else {},
        })
        self._original.publish(data, metadata=metadata, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._original, name)


def extract_display_data(
    outputs: list[dict],
    execution_count: int,
    cell_id: str = "",
    max_text_length: int = 10_000,
) -> list[dict]:
    """Convert captured display outputs to trace event payloads.

    Args:
        outputs: Raw display data from DisplayCapture.uninstall().
        execution_count: Cell execution count.
        cell_id: Notebook cell ID.
        max_text_length: Truncate text content beyond this.

    Returns:
        List of payload dicts for DISPLAY_DATA events.
    """
    results = []
    for idx, output in enumerate(outputs):
        data = output.get("data", {})
        if not data:
            continue

        # Build a cleaned mime bundle
        mime_bundle: dict[str, str] = {}
        for mime_type, content in data.items():
            if mime_type in ("image/png", "image/jpeg", "image/svg+xml"):
                # Already base64 for PNG/JPEG from inline backend
                if isinstance(content, bytes):
                    mime_bundle[mime_type] = base64.b64encode(content).decode(
                        "ascii"
                    )
                else:
                    mime_bundle[mime_type] = str(content)
            elif mime_type in ("text/plain", "text/html", "text/latex"):
                text = str(content)
                if len(text) > max_text_length:
                    text = text[:max_text_length]
                mime_bundle[mime_type] = text
            else:
                # Other MIME types: store as string, truncate
                text = str(content)
                if len(text) > max_text_length:
                    text = text[:max_text_length]
                mime_bundle[mime_type] = text

        results.append({
            "cell_id": cell_id,
            "execution_count": execution_count,
            "display_index": idx,
            "mime_bundle": mime_bundle,
        })

    return results


# --- Stdout / stderr capture ---


class StreamCapture:
    """Context manager that captures writes to stdout and stderr.

    Usage::

        with StreamCapture() as cap:
            print("hello")
        cap.stdout_text  # "hello\\n"
        cap.stderr_text  # ""
    """

    def __init__(self, max_chars: int = 50_000):
        self.max_chars = max_chars
        self._stdout_buf = io.StringIO()
        self._stderr_buf = io.StringIO()
        self._orig_stdout: Any = None
        self._orig_stderr: Any = None
        self._tee_stdout: _TeeWriter | None = None
        self._tee_stderr: _TeeWriter | None = None

    def __enter__(self) -> StreamCapture:
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr
        self._tee_stdout = _TeeWriter(self._orig_stdout, self._stdout_buf)
        self._tee_stderr = _TeeWriter(self._orig_stderr, self._stderr_buf)
        sys.stdout = self._tee_stdout  # type: ignore[assignment]
        sys.stderr = self._tee_stderr  # type: ignore[assignment]
        return self

    def __exit__(self, *_: object) -> None:
        sys.stdout = self._orig_stdout
        sys.stderr = self._orig_stderr

    @property
    def stdout_text(self) -> str:
        text = self._stdout_buf.getvalue()
        if len(text) > self.max_chars:
            return text[: self.max_chars]
        return text

    @property
    def stderr_text(self) -> str:
        text = self._stderr_buf.getvalue()
        if len(text) > self.max_chars:
            return text[: self.max_chars]
        return text

    @property
    def stdout_truncated(self) -> bool:
        return len(self._stdout_buf.getvalue()) > self.max_chars

    @property
    def stderr_truncated(self) -> bool:
        return len(self._stderr_buf.getvalue()) > self.max_chars


class _TeeWriter:
    """Writes to two streams simultaneously."""

    def __init__(self, original: Any, capture: io.StringIO):
        self._original = original
        self._capture = capture

    def write(self, text: str) -> int:
        self._capture.write(text)
        return self._original.write(text)

    def flush(self) -> None:
        self._original.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._original, name)


# --- Cell output extraction ---


def extract_cell_outputs(
    result: Any,
    cell_id: str = "",
    max_content_length: int = 10_000,
) -> list[dict]:
    """Extract output data from an IPython ExecutionResult.

    Args:
        result: IPython ExecutionResult from post_run_cell callback.
        cell_id: Notebook cell ID.
        max_content_length: Truncate content beyond this length.

    Returns:
        List of output dicts with mime_type, content, truncated.
    """
    outputs = []
    execution_count = getattr(result, "execution_count", 0) or 0

    # Cell return value (the repr displayed below the cell)
    if result.result is not None:
        content = repr(result.result)
        truncated = len(content) > max_content_length
        if truncated:
            content = content[:max_content_length]
        outputs.append({
            "cell_id": cell_id,
            "execution_count": execution_count,
            "mime_type": "text/plain",
            "content": content,
            "stream": "",
            "truncated": truncated,
        })

    return outputs


def extract_cell_error(result: Any, cell_id: str = "") -> dict | None:
    """Extract error information from an IPython ExecutionResult.

    Args:
        result: IPython ExecutionResult from post_run_cell callback.
        cell_id: Notebook cell ID.

    Returns:
        Error dict with ename, evalue, traceback_lines, or None if no error.
    """
    error = result.error_in_exec or result.error_before_exec
    if error is None:
        return None

    execution_count = getattr(result, "execution_count", 0) or 0
    ename = type(error).__name__
    evalue = str(error)

    # Extract traceback lines, limit to last 20
    tb_lines: list[str] = []
    try:
        import traceback

        tb_lines = traceback.format_exception(
            type(error), error, error.__traceback__
        )
        # Flatten and limit
        flat_lines: list[str] = []
        for line in tb_lines:
            flat_lines.extend(line.splitlines())
        tb_lines = flat_lines[-20:]
    except Exception:  # pylint: disable=broad-except
        pass

    return {
        "cell_id": cell_id,
        "execution_count": execution_count,
        "ename": ename,
        "evalue": evalue,
        "traceback_lines": tb_lines,
    }
