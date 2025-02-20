import hashlib
import lzma
import pickle
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from loguru import logger

from ..cli.config import get_config_value

__current_config_cache = None


@dataclass
class Report():
    workflow: str = ''
    in_spec: bool = False
    bad_data: bool = False
    fully_calibrated: bool = False
    calibrated_time: datetime = field(default_factory=datetime.now)
    checked_time: datetime = field(default_factory=datetime.now)
    ttl: timedelta = timedelta(days=3650)
    parameters: dict = field(default_factory=dict)
    oracle: dict = field(default_factory=dict)
    other_infomation: dict = field(default_factory=dict)
    data: Any = field(default_factory=tuple, repr=False)
    index: int = -1
    previous_path: Path | None = field(default=None, repr=False)
    heads: dict[str, Path] = field(default_factory=dict, repr=False)
    base_path: Path | None = field(default=None, repr=False)
    path: Path | None = field(default=None, repr=False)
    config_path: Path | None = field(default=None, repr=False)

    @property
    def previous(self):
        if self.previous_path is not None and self.base_path is not None:
            return load_report(self.previous_path, self.base_path)
        else:
            return None

    @property
    def state(self) -> Literal['OK', 'Bad', 'Outdated']:
        state = 'Bad'
        match (self.in_spec, self.bad_data):
            case (True, False):
                state = 'OK'
            case (False, True):
                state = 'Bad'
            case (False, False):
                state = 'Outdated'
        return state

    @property
    def config(self):
        if self.config_path is not None and self.base_path is not None:
            return load_config(self.config_path, self.base_path)
        else:
            return None

    @state.setter
    def state(self, state: Literal['OK', 'Bad', 'Outdated', 'In spec',
                                   'Out of spec', 'Bad data']):
        if state not in [
                'OK', 'Bad', 'Outdated', 'In spec', 'Out of spec', 'Bad data'
        ]:
            raise ValueError(
                f'Invalid state: {state}, state must be one of "OK", "Bad" and "Outdated"'
            )
        if state in ['In spec', 'OK']:
            self.in_spec = True
            self.bad_data = False
        elif state in ['Bad data', 'Bad']:
            self.bad_data = True
            self.in_spec = False
        else:
            self.bad_data = False
            self.in_spec = False


def random_path(base: Path) -> Path:
    while True:
        s = uuid.uuid4().hex
        path = Path(s[:2]) / s[2:4] / s[4:6] / s[6:]
        if not (base / path).exists():
            return path


def save_config_key_history(key: str, report: Report,
                            base_path: str | Path) -> int:
    global __current_config_cache
    base_path = Path(base_path) / 'state'
    base_path.mkdir(parents=True, exist_ok=True)

    if __current_config_cache is None:
        if (base_path / 'parameters.pkl').exists():
            with open(base_path / 'parameters.pkl', 'rb') as f:
                __current_config_cache = pickle.load(f)
        else:
            __current_config_cache = {}

    __current_config_cache[
        key] = report.data, report.calibrated_time, report.checked_time

    with open(base_path / 'parameters.pkl', 'wb') as f:
        pickle.dump(__current_config_cache, f)
    return 0


def find_config_key_history(key: str, base_path: str | Path) -> Report | None:
    global __current_config_cache
    base_path = Path(base_path) / 'state'
    if __current_config_cache is None:
        if (base_path / 'parameters.pkl').exists():
            with open(base_path / 'parameters.pkl', 'rb') as f:
                __current_config_cache = pickle.load(f)
        else:
            __current_config_cache = {}

    if key in __current_config_cache:
        value, calibrated_time, checked_time = __current_config_cache.get(
            key, None)
        report = Report(
            workflow=f'cfg:{key}',
            bad_data=False,
            in_spec=True,
            fully_calibrated=True,
            parameters={key: value},
            data=value,
            calibrated_time=calibrated_time,
            checked_time=checked_time,
        )
        return report
    return None


def save_report(workflow: str,
                report: Report,
                base_path: str | Path,
                overwrite: bool = False,
                refresh_heads: bool = True) -> int:
    if workflow.startswith("cfg:"):
        return save_config_key_history(workflow[4:], report, base_path)

    logger.debug(
        f'Saving report for "{workflow}", {report.in_spec=}, {report.bad_data=}, {report.fully_calibrated=}'
    )
    base_path = Path(base_path)
    try:
        buf = lzma.compress(pickle.dumps(report))
    except:
        raise ValueError(f"Can't pickle report for {workflow}")
    if overwrite:
        path = report.path
        if path is None:
            raise ValueError("Report path is None, can't overwrite.")
        with open(base_path / 'objects' / path, "rb") as f:
            index = int.from_bytes(f.read(8), 'big')
        report.index = index
    else:
        path = random_path(base_path / 'objects')
        (base_path / 'objects' / path).parent.mkdir(parents=True,
                                                    exist_ok=True)
        report.path = path
        report.index = create_index("report",
                                    base_path,
                                    context=str(path),
                                    width=35)
    with open(base_path / 'objects' / path, "wb") as f:
        f.write(report.index.to_bytes(8, 'big'))
        f.write(buf)
    if refresh_heads:
        set_head(workflow, path, base_path)
    return report.index


def load_report(path: str | Path, base_path: str | Path) -> Report | None:
    base_path = Path(base_path)
    path = base_path / 'objects' / path

    with open(base_path / 'objects' / path, "rb") as f:
        index = int.from_bytes(f.read(8), 'big')
        report = pickle.loads(lzma.decompress(f.read()))
        report.base_path = base_path
        report.index = index
        return report


def find_report(
    workflow: str, base_path: str | Path = get_config_value("data", Path)
) -> Report | None:
    if workflow.startswith("cfg:"):
        return find_config_key_history(workflow[4:], base_path)

    base_path = Path(base_path)
    path = get_head(workflow, base_path)
    if path is None:
        return None
    return load_report(path, base_path)


def renew_report(workflow: str, report: Report | None, base_path: str | Path):
    logger.debug(f'Renewing report for "{workflow}"')
    if report is not None:
        report.checked_time = datetime.now()
        return save_report(workflow,
                           report,
                           base_path,
                           overwrite=True,
                           refresh_heads=True)
    else:
        raise ValueError(f"Can't renew report for {workflow}")


def revoke_report(workflow: str, report: Report | None, base_path: str | Path):
    logger.debug(f'Revoking report for "{workflow}"')
    base_path = Path(base_path)
    if report is not None:
        report.in_spec = False
        report.previous_path = report.path
        return save_report(workflow,
                           report,
                           base_path,
                           overwrite=False,
                           refresh_heads=True)


def set_head(workflow: str, path: Path, base_path: str | Path):
    base_path = Path(base_path)
    base_path.mkdir(parents=True, exist_ok=True)
    try:
        with open(base_path / "heads", "rb") as f:
            heads = pickle.load(f)
    except:
        heads = {}
    heads[workflow] = path
    with open(base_path / "heads", "wb") as f:
        pickle.dump(heads, f)


def get_head(workflow: str, base_path: str | Path) -> Path | None:
    base_path = Path(base_path)
    try:
        with open(base_path / "heads", "rb") as f:
            heads = pickle.load(f)
        return heads[workflow]
    except:
        return None


def get_heads(base_path: str | Path) -> Path | None:
    base_path = Path(base_path)
    try:
        with open(base_path / "heads", "rb") as f:
            heads = pickle.load(f)
        return heads
    except:
        return {}


def create_index(name: str,
                 base_path: str | Path,
                 context: str,
                 width: int = -1,
                 start: int = 0):

    path = Path(base_path) / "index" / name
    if width == -1:
        width = len(context)
    else:
        width = max(width, len(context))

    if path.with_suffix('.width').exists():
        width = int(path.with_suffix('.width').read_text())
        index = int(path.with_suffix('.seq').read_text())
    else:
        index = start
    if width < len(context):
        raise ValueError(
            f"Context '{context}' is too long, existing width of '{name}' is {width}."
        )
    if not path.with_suffix('.width').exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.with_suffix('.width').write_text(str(width))

    path.with_suffix('.seq').write_text(str(index + 1))

    with path.with_suffix('.idx').open("a") as f:
        f.write(f"{context.ljust(width)}\n")

    return index


@lru_cache(maxsize=4096)
def query_index(name: str, base_path: str | Path, index: int):
    path = Path(base_path) / "index" / name
    width = int(path.with_suffix('.width').read_text())

    with path.with_suffix('.idx').open("r") as f:
        f.seek(index * (width + 1))
        context = f.read(width)
    return context.rstrip()


def get_report_by_index(
    index: int, base_path: str | Path = get_config_value("data", Path)
) -> Report | None:
    try:
        path = query_index("report", base_path, index)
        return load_report(path, base_path)
    except:
        return None


def save_config(cfg, data_path):
    i = 0
    buf = pickle.dumps(cfg)
    buf = lzma.compress(buf)
    h = hashlib.md5(buf)

    while True:
        salt = f"{i}".encode()
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
    return str(cfg_id)


@lru_cache(maxsize=1024)
def load_config(id, data_path):
    path = Path(data_path) / 'config' / id
    with open(path, 'rb') as f:
        buf = f.read()
    cfg = pickle.loads(lzma.decompress(buf))
    return cfg
