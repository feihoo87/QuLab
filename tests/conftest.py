import asyncio
import logging
import os
import platform
import tempfile
from pathlib import Path

import pytest

log = logging.getLogger()
log.setLevel(logging.DEBUG)


# Configure pytest-asyncio
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


def pytest_collection_modifyitems(config, items):
    if platform.system() != 'Windows':
        # --runslow given in cli: do not skip slow tests
        return
    skip_windows = pytest.mark.skip(reason="could not run on windows.")
    for item in items:
        if "not_on_windows" in item.keywords:
            item.add_marker(skip_windows)
