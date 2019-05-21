import os
import platform
from pathlib import Path

import yaml
from qulab.utils import getHostIP

CONFIG_DIRNAME = 'QuLab'
CONFIG_FILENAME = 'config.yml'
CONFIG_DRIVERDIRNAME = 'drivers'


def load_config(path):
    return yaml.load(path.read_text(), Loader=yaml.FullLoader)


def config_dir():
    if platform.system() in ['Darwin', 'Linux']:
        home = os.getenv('HOME')
    elif platform.system() == 'Windows':
        home = os.getenv('ProgramData')
    else:
        home = Path.home()
    return Path(home) / CONFIG_DIRNAME


def config_file():
    return config_dir() / CONFIG_FILENAME


def default_config():
    return {
        'db': {
            'db': 'lab',
            'host': 'localhost'
        },
        'log': {
            'level': 'info',
            'server': 'tcp://127.0.0.1:16872',
        },
        'dht': {
            'default_port': 8987,
            'bootstrap_nodes': [f'kad://{getHostIP()}:8987'],
            'white_list': [],
            'black_list': [],
        },
        'drivers': [str(config_dir() / CONFIG_DRIVERDIRNAME)],
        'data_path': str(Path.home() / 'QuLabData')
    }  # yapf : disable


def create_config_file():
    config_dir().mkdir(parents=True, exist_ok=True)
    config_file().write_text(yaml.dump(default_config()))


if config_file().exists():
    config = load_config(config_file())
else:
    config = default_config()
