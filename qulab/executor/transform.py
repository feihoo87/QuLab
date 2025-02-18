import functools
import hashlib
import lzma
import pickle
from pathlib import Path

from .storage import Result

__config_id = None


def _query_config(name: str, default=None):
    import pickle

    try:
        with open('parameters.pkl', 'rb') as f:
            parameters = pickle.load(f)
    except:
        parameters = {}

    return parameters.get(name, default)


def _update_config(updates):
    import pickle

    try:
        with open('parameters.pkl', 'rb') as f:
            parameters = pickle.load(f)
    except:
        parameters = {}

    for k, v in updates.items():
        parameters[k] = v

    with open('parameters.pkl', 'wb') as f:
        pickle.dump(parameters, f)


def _export_config() -> dict:
    import pickle

    try:
        with open('parameters.pkl', 'rb') as f:
            parameters = pickle.load(f)
    except:
        parameters = {}

    return parameters


def update_parameters(result: Result, data_path):
    global __config_id
    update_config(result.parameters)
    cfg = export_config()
    __config_id = _save_config(cfg, data_path)


def current_config(data_path):
    global __config_id
    if __config_id is None:
        cfg = export_config()
        __config_id = _save_config(cfg, data_path)
    return __config_id


def _save_config(cfg, data_path):
    global __config_id
    i = 0
    buf = pickle.dumps(cfg)
    buf = lzma.compress(buf)
    h = hashlib.md5(buf)

    while True:
        salt = f"{i:08d}".encode()
        h.update(salt)
        hashstr = h.hexdigest()
        cfg_id = Path(hashstr[:2]) / hashstr[2:4] / hashstr[4:]
        path = Path(data_path) / 'config' / cfg_id
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'wb') as f:
                f.write(buf)
            break
        elif path.read_bytes() == buf:
            break
        i += 1
    __config_id = str(cfg_id)
    return __config_id


@functools.lru_cache(maxsize=1024)
def _load_config(id, data_path):
    path = Path(data_path) / 'config' / id
    with open(path, 'rb') as f:
        buf = f.read()
    cfg = pickle.loads(lzma.decompress(buf))
    return cfg


query_config = _query_config
update_config = _update_config
export_config = _export_config


def set_config_api(query_method, update_method, export_method):
    """
    Set the query and update methods for the config.

    Args:
        query_method: The query method.
            the method should take a key and return the value.
        update_method: The update method.
            the method should take a dict of updates.
    """
    global query_config, update_config, export_config

    query_config = query_method
    update_config = update_method
    export_config = export_method

    return query_config, update_config, export_config
