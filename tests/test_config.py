import os
import platform
import tempfile
from pathlib import Path

import pytest
from qulab._config import config_dir, config_file, load_config

config_str = """
db:
  db: lab
  host: localhost
"""


@pytest.yield_fixture
def tmp_config_file():
    with tempfile.NamedTemporaryFile('w', delete=False) as f:
        f.write(config_str)
        p = Path(f.name)
    try:
        yield p
    finally:
        p.unlink()


def test_config_dir():
    if platform.system() in ['Darwin', 'Linux']:
        home = os.getenv('HOME')
    elif platform.system() == 'Windows':
        home = os.getenv('ProgramData')
    else:
        home = os.getcwd()
    assert config_dir() == Path(home) / 'QuLab'


def test_config_file():
    assert config_file() == config_dir() / 'config.yaml'


def test_load_config(tmp_config_file):
    config = load_config(tmp_config_file)
    assert config['db']['db'] == 'lab'
