"""Shared fixtures for storage tests."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from qulab.storage.local import LocalStorage
from qulab.storage.models.base import Base, SessionManager


@pytest.fixture
def temp_storage_path(tmp_path: Path) -> Path:
    """Create a temporary storage directory."""
    return tmp_path / "storage"


@pytest.fixture
def local_storage(temp_storage_path: Path) -> LocalStorage:
    """Create a LocalStorage instance with a temporary directory."""
    return LocalStorage(base_path=temp_storage_path)


@pytest.fixture
def sample_document_data() -> dict[str, Any]:
    """Return sample document data."""
    return {
        "title": "Test Document",
        "content": {"key1": "value1", "key2": 42, "nested": {"a": 1, "b": 2}},
        "measurements": [1.0, 2.0, 3.0, 4.0, 5.0],
    }


@pytest.fixture
def sample_dataset_desc() -> dict[str, Any]:
    """Return sample dataset description."""
    return {
        "app": "test_app",
        "version": "1.0.0",
        "parameters": {"frequency": 5.2e9, "amplitude": 0.5},
        "notes": "Test dataset for unit tests",
    }


@pytest.fixture
def sample_config() -> dict[str, Any]:
    """Return sample configuration dictionary."""
    return {
        "scan": {
            "type": "1D",
            "start": 0.0,
            "stop": 10.0,
            "step": 0.1,
        },
        "instruments": ["qubit", "readout", "mixer"],
        "settings": {"averages": 1000, "trigger": "internal"},
    }


@pytest.fixture
def sample_script() -> str:
    """Return sample script code."""
    return '''
def run_experiment(config):
    """Run a test experiment."""
    results = []
    for i in range(config['scan']['steps']):
        value = config['scan']['start'] + i * config['scan']['step']
        results.append(measure(value))
    return results

def measure(x):
    return x ** 2 + np.random.randn() * 0.1
'''


@pytest.fixture
def sample_script_alternate() -> str:
    """Return an alternate sample script for deduplication tests."""
    return '''
def another_function():
    """A different script."""
    return 42
'''


@pytest.fixture
def complex_config() -> dict[str, Any]:
    """Return a more complex configuration for testing."""
    return {
        "nested": {
            "deeply": {
                "nested": {
                    "value": [1, 2, 3, {"key": "value"}],
                },
            },
        },
        "arrays": np.array([1, 2, 3]).tolist(),
        "unicode": "测试中文和🎉表情符号",
        "numbers": [1, 1.5, 1e-10, 1e10],
        "boolean": True,
        "null_value": None,
    }


@pytest.fixture
def sample_tags() -> list[str]:
    """Return sample tags."""
    return ["test", "calibration", "qubit-1"]


@pytest.fixture
def sample_numpy_data() -> dict[str, np.ndarray]:
    """Return sample numpy arrays for dataset testing."""
    return {
        "x": np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
        "y": np.array([1.0, 4.0, 9.0, 16.0, 25.0]),
        "complex": np.array([1+2j, 3+4j, 5+6j]),
    }


@pytest.fixture
def session_manager(local_storage: LocalStorage) -> SessionManager:
    """Get the session manager from local storage."""
    return local_storage._session_manager


@pytest.fixture
def db_session(local_storage: LocalStorage):
    """Provide a database session for testing."""
    from sqlalchemy.orm import Session
    session = local_storage._get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture
def clean_storage(temp_storage_path: Path):
    """Create a completely fresh storage instance for isolation tests."""
    storage = LocalStorage(base_path=temp_storage_path)
    yield storage
    # Cleanup handled by tmp_path fixture
