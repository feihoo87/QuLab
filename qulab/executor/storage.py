import lzma
import pickle
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

from ..cli.config import get_config_value


@dataclass
class Result():
    in_spec: bool = False
    bad_data: bool = False
    fully_calibrated: bool = False
    calibrated_time: datetime = field(default_factory=datetime.now)
    checked_time: datetime = field(default_factory=datetime.now)
    ttl: timedelta = timedelta(days=3650)
    params: dict = field(default_factory=dict)
    info: dict = field(default_factory=dict)
    data: tuple = field(default_factory=tuple)
    index: int = -1
    previous_path: Path | None = None
    base_path: Path | None = None

    @property
    def previous(self):
        if self.previous_path is not None and self.base_path is not None:
            return load_result(self.previous_path, self.base_path)
        else:
            return None


def random_path(base: Path) -> Path:
    while True:
        s = uuid.uuid4().hex
        path = Path(s[:2]) / s[2:4] / s[4:6] / s[6:]
        if not (base / path).exists():
            return path


def save_result(workflow: str,
                result: Result,
                base_path: str | Path,
                overwrite: bool = False):
    logger.debug(
        f'Saving result for "{workflow}", {result.in_spec=}, {result.bad_data=}, {result.fully_calibrated=}'
    )
    base_path = Path(base_path)
    if overwrite:
        buf = lzma.compress(pickle.dumps(result))
        path = get_head(workflow, base_path)
        with open(base_path / 'objects' / path, "rb") as f:
            index = int.from_bytes(f.read(8), 'big')
        result.index = index
    else:
        result.previous_path = get_head(workflow, base_path)
        buf = lzma.compress(pickle.dumps(result))
        path = random_path(base_path / 'objects')
        (base_path / 'objects' / path).parent.mkdir(parents=True,
                                                    exist_ok=True)
        result.index = create_index("result",
                                    base_path,
                                    context=str(path),
                                    width=35)

    with open(base_path / 'objects' / path, "wb") as f:
        f.write(result.index.to_bytes(8, 'big'))
        f.write(buf)
    set_head(workflow, path, base_path)


def load_result(path: str | Path, base_path: str | Path) -> Result | None:
    base_path = Path(base_path)
    path = base_path / 'objects' / path

    with open(base_path / 'objects' / path, "rb") as f:
        index = int.from_bytes(f.read(8), 'big')
        result = pickle.loads(lzma.decompress(f.read()))
        result.base_path = base_path
        result.index = index
        return result


def find_result(
    workflow: str, base_path: str | Path = get_config_value("data", Path)
) -> Result | None:
    base_path = Path(base_path)
    path = get_head(workflow, base_path)
    if path is None:
        return None
    return load_result(path, base_path)


def renew_result(workflow: str, base_path: str | Path):
    logger.debug(f'Renewing result for "{workflow}"')
    result = find_result(workflow, base_path)
    if result is not None:
        result.checked_time = datetime.now()
        save_result(workflow, result, base_path)


def revoke_result(workflow: str, base_path: str | Path):
    logger.debug(f'Revoking result for "{workflow}"')
    base_path = Path(base_path)
    path = get_head(workflow, base_path)
    if path is not None:
        with open(base_path / 'objects' / path, "rb") as f:
            result = pickle.load(f)
        result.in_spec = False
        save_result(workflow, result, base_path)


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
                 width: int,
                 start: int = 0):
    path = Path(base_path) / "index" / f"{name}.seq"
    if path.exists():
        with open(path, "r") as f:
            index = int(f.read())
    else:
        index = start
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(str(index + 1))

    path = Path(base_path) / "index" / f"{name}.width"
    with open(path, "w") as f:
        f.write(str(width))

    path = Path(base_path) / "index" / f"{name}.idx"
    with open(path, "a") as f:

        f.write(f"{context.ljust(width)}\n")

    return index


def query_index(name: str, base_path: str | Path, index: int):
    path = Path(base_path) / "index" / f"{name}.width"
    with open(path, "r") as f:
        width = int(f.read())
    path = Path(base_path) / "index" / f"{name}.idx"
    with open(path, "r") as f:
        f.seek(index * (width + 1))
        context = f.read(width)
    return context.rstrip()


def get_result_by_index(
    index: int, base_path: str | Path = get_config_value("data", Path)
) -> Result | None:
    path = query_index("result", base_path, index)
    return load_result(path, base_path)
