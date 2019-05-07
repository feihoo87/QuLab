import os
import platform
import tempfile
from pathlib import Path

import pytest


def pytest_collection_modifyitems(config, items):
    if platform.system() != 'Windows':
        # --runslow given in cli: do not skip slow tests
        return
    skip_windows = pytest.mark.skip(reason="could not run on windows.")
    for item in items:
        if "not_on_windows" in item.keywords:
            item.add_marker(skip_windows)
