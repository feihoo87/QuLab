import importlib
import logging
from pathlib import Path

from qulab._config import config

log = logging.getLogger(__name__)


def find_location(name):
    for path in config.get('drivers', []):
        p = Path(path) / (name+'.py')
        if p.exists() and p.is_file():
            return p
        p = Path(path) / name
        if p.exists() and p.is_dir():
            return p
    return None


def loadDriver(name):
    location = find_location(name)
    if location is None:
        try:
            mod = importlib.import_module(f'qulab.drivers.{name}')
        except:
            return None
    else:
        spec = importlib.util.spec_from_file_location(f'qulab.drivers.{name}',
                                                      location)
        mod = importlib.util.module_from_spec(spec)
    return getattr(mod, 'Driver')
