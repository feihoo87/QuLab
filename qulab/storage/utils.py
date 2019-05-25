import time
from pathlib import Path

import numpy as np
from qulab import config

storage_cfg = config.get('storage', {})


def save(title, *args, base_path=None, **kw):
    if base_path is None:
        base_path = Path(storage_cfg.get('data_path', Path.cwd()))
    else:
        base_path = Path(base_path)

    path = base_path / time.strftime('%Y') / time.strftime('%m%d')
    fname = f"{title}_{time.strftime('%Y%m%d%H%M%S')}.npz"
    path.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path / fname, *args, **kw)
    return path / fname
