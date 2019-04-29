import os
import platform
from pathlib import Path

import yaml

CONFIG_DIRNAME = 'QuLab'
CONFIG_FILENAME = 'config.yaml'
DEFAULT_CONFIG = {'db': {'db': 'lab', 'host': 'localhost'}}


def load_config(path):
    return yaml.load(path.read_text(), Loader=yaml.FullLoader)


def config_dir():
    if platform.system() in ['Darwin', 'Linux']:
        home = os.getenv('HOME')
    elif platform.system() == 'Windows':
        home = os.getenv('ProgramData')
    else:
        home = os.getcwd()
    return Path(home) / CONFIG_DIRNAME


def config_file():
    return config_dir() / CONFIG_FILENAME


if config_file().exists():
    config = load_config(config_file())
else:
    config = DEFAULT_CONFIG
