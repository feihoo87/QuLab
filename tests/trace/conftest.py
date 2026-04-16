"""Shared fixtures for trace tests."""

import pytest
from pathlib import Path


@pytest.fixture
def tmp_data_path(tmp_path):
    """Provide a temporary data path for storage tests."""
    data = tmp_path / "data"
    data.mkdir()
    return data


@pytest.fixture
def tmp_buffer_dir(tmp_path):
    """Provide a temporary buffer directory for client tests."""
    buf = tmp_path / "buffer"
    buf.mkdir()
    return buf
