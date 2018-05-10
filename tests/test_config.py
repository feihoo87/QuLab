import pytest

from qulab.config import *


def test_config_dir():
    assert isinstance(config_dir(), Path)
