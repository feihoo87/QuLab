"""Tests for qulab.trace.capture."""

from unittest.mock import MagicMock

from qulab.trace.capture import (
    DisplayCapture,
    StreamCapture,
    extract_cell_error,
    extract_cell_outputs,
    extract_display_data,
)


class TestStreamCapture:
    def test_captures_stdout(self):
        with StreamCapture() as cap:
            print("hello")
        assert "hello" in cap.stdout_text

    def test_captures_stderr(self):
        import sys

        with StreamCapture() as cap:
            sys.stderr.write("error msg")
        assert "error msg" in cap.stderr_text

    def test_truncation(self):
        with StreamCapture(max_chars=10) as cap:
            print("a" * 100)
        assert len(cap.stdout_text) == 10
        assert cap.stdout_truncated

    def test_no_truncation(self):
        with StreamCapture(max_chars=1000) as cap:
            print("short")
        assert not cap.stdout_truncated

    def test_restores_streams(self):
        import sys

        orig_stdout = sys.stdout
        orig_stderr = sys.stderr
        with StreamCapture():
            pass
        assert sys.stdout is orig_stdout
        assert sys.stderr is orig_stderr


class TestDisplayCapture:
    def test_no_ipython_returns_empty(self):
        cap = DisplayCapture()
        cap.install()
        outputs = cap.uninstall()
        # Without IPython, install is a no-op, returns empty
        assert isinstance(outputs, list)


class TestExtractDisplayData:
    def test_empty_outputs(self):
        result = extract_display_data([], execution_count=1)
        assert result == []

    def test_image_output(self):
        outputs = [
            {"data": {"image/png": "iVBOR_base64data", "text/plain": "<Figure>"}, "metadata": {}},
        ]
        result = extract_display_data(outputs, execution_count=1, cell_id="c1")
        assert len(result) == 1
        assert result[0]["cell_id"] == "c1"
        assert result[0]["execution_count"] == 1
        assert result[0]["display_index"] == 0
        assert "image/png" in result[0]["mime_bundle"]
        assert "text/plain" in result[0]["mime_bundle"]

    def test_multiple_outputs(self):
        outputs = [
            {"data": {"text/html": "<b>bold</b>"}, "metadata": {}},
            {"data": {"image/png": "data2"}, "metadata": {}},
        ]
        result = extract_display_data(outputs, execution_count=2)
        assert len(result) == 2
        assert result[0]["display_index"] == 0
        assert result[1]["display_index"] == 1

    def test_truncation(self):
        outputs = [
            {"data": {"text/plain": "x" * 20_000}, "metadata": {}},
        ]
        result = extract_display_data(outputs, execution_count=1, max_text_length=100)
        assert len(result[0]["mime_bundle"]["text/plain"]) == 100


class TestExtractCellOutputs:
    def test_with_result(self):
        result = MagicMock()
        result.result = 42
        result.execution_count = 1
        outputs = extract_cell_outputs(result, cell_id="c1")
        assert len(outputs) == 1
        assert outputs[0]["mime_type"] == "text/plain"
        assert "42" in outputs[0]["content"]
        assert outputs[0]["cell_id"] == "c1"

    def test_none_result(self):
        result = MagicMock()
        result.result = None
        outputs = extract_cell_outputs(result)
        assert outputs == []

    def test_truncation(self):
        result = MagicMock()
        result.result = "x" * 20_000
        result.execution_count = 1
        outputs = extract_cell_outputs(result, max_content_length=100)
        assert len(outputs) == 1
        assert outputs[0]["truncated"]
        assert len(outputs[0]["content"]) == 100


class TestExtractCellError:
    def test_no_error(self):
        result = MagicMock()
        result.error_in_exec = None
        result.error_before_exec = None
        assert extract_cell_error(result) is None

    def test_with_error(self):
        result = MagicMock()
        result.error_before_exec = None
        result.error_in_exec = ValueError("bad value")
        result.execution_count = 1
        error = extract_cell_error(result, cell_id="c1")
        assert error is not None
        assert error["ename"] == "ValueError"
        assert error["evalue"] == "bad value"
        assert error["cell_id"] == "c1"
