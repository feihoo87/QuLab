import hashlib
import lzma
import pickle
import re
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qs

from loguru import logger

try:
    from paramiko import SSHClient
    from paramiko.ssh_exception import SSHException
except:
    import warnings

    warnings.warn("Can't import paramiko, ssh support will be disabled.")

    class SSHClient:

        def __init__(self):
            raise ImportError(
                "Can't import paramiko, ssh support will be disabled.")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

    class SSHException(Exception):
        pass


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
    base_path: str | Path | None = field(default=None, repr=False)
    path: Path | None = field(default=None, repr=False)
    config_path: Path | None = field(default=None, repr=False)
    script_path: Path | None = field(default=None, repr=False)

    def __getstate__(self):
        state = self.__dict__.copy()
        state.pop('base_path')
        for k in ['path', 'previous_path', 'config_path', 'script_path']:
            if state[k] is not None:
                state[k] = str(state[k])
        return state

    def __setstate__(self, state):
        for k in ['path', 'previous_path', 'config_path', 'script_path']:
            if state[k] is not None:
                state[k] = Path(state[k])
        self.__dict__.update(state)

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

    @property
    def config(self):
        if self.config_path is not None and self.base_path is not None:
            return load_item(self.config_path, self.base_path)
        else:
            return None

    @property
    def script(self):
        if self.script_path is not None and self.base_path is not None:
            source = load_item(self.script_path, self.base_path)
            if isinstance(source, str):
                return source
            else:
                from .template import inject_mapping
                return inject_mapping(*source)[0]
        else:
            return None

    @property
    def template_source(self):
        if self.script_path is not None and self.base_path is not None:
            source = load_item(self.script_path, self.base_path)
            return source
        else:
            return None


def random_path(base: Path) -> Path:
    while True:
        s = uuid.uuid4().hex
        path = Path(s[:2]) / s[2:4] / s[4:6] / s[6:]
        if not (base / path).exists():
            return path


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


def get_report_by_index(
    index: int, base_path: str | Path = get_config_value("data", Path)
) -> Report | None:
    try:
        path = query_index("report", base_path, index)
        return load_report(path, base_path)
    except:
        raise
        return None


def get_head(workflow: str, base_path: str | Path) -> Path | None:
    return get_heads(base_path).get(workflow, None)


#########################################################################
##                           Basic Write API                           ##
#########################################################################


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
        with open(base_path / 'reports' / path, "rb") as f:
            index = int.from_bytes(f.read(8), 'big')
        report.index = index
    else:
        path = random_path(base_path / 'reports')
        (base_path / 'reports' / path).parent.mkdir(parents=True,
                                                    exist_ok=True)
        report.path = path
        report.index = create_index("report",
                                    base_path,
                                    context=str(path),
                                    width=35)
    with open(base_path / 'reports' / path, "wb") as f:
        f.write(report.index.to_bytes(8, 'big'))
        f.write(buf)
    if refresh_heads:
        set_head(workflow, path, base_path)
    return report.index


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


def save_item(item, data_path):
    salt = 0
    buf = pickle.dumps(item)
    buf = lzma.compress(buf)
    h = hashlib.md5(buf)

    while True:
        h.update(f"{salt}".encode())
        hashstr = h.hexdigest()
        item_id = Path(hashstr[:2]) / hashstr[2:4] / hashstr[4:]
        path = Path(data_path) / 'items' / item_id
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'wb') as f:
                f.write(buf)
            break
        elif path.read_bytes() == buf:
            break
        salt += 1
    return str(item_id)


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


#########################################################################
##                            Basic Read API                           ##
#########################################################################


def load_report(path: str | Path, base_path: str | Path) -> Report | None:
    if isinstance(base_path, str) and base_path.startswith('ssh://'):
        with SSHClient() as client:
            cfg = parse_ssh_uri(base_path)
            remote_base_path = cfg.pop('remote_file_path')
            client.load_system_host_keys()
            client.connect(**cfg)
            report = load_report_from_scp(path, remote_base_path, client)
            report.base_path = base_path
            return report

    base_path = Path(base_path)
    if zipfile.is_zipfile(base_path):
        return load_report_from_zipfile(path, base_path)

    path = base_path / 'reports' / path

    with open(base_path / 'reports' / path, "rb") as f:
        index = int.from_bytes(f.read(8), 'big')
        report = pickle.loads(lzma.decompress(f.read()))
        report.base_path = base_path
        report.index = index
        return report


def get_heads(base_path: str | Path) -> Path | None:
    if isinstance(base_path, str) and base_path.startswith('ssh://'):
        with SSHClient() as client:
            cfg = parse_ssh_uri(base_path)
            remote_base_path = cfg.pop('remote_file_path')
            client.load_system_host_keys()
            client.connect(**cfg)
            return get_heads_from_scp(remote_base_path, client)

    base_path = Path(base_path)
    if zipfile.is_zipfile(base_path):
        return get_heads_from_zipfile(base_path)
    try:
        with open(base_path / "heads", "rb") as f:
            heads = pickle.load(f)
        return heads
    except:
        return {}


@lru_cache(maxsize=4096)
def query_index(name: str, base_path: str | Path, index: int):
    if isinstance(base_path, str) and base_path.startswith('ssh://'):
        with SSHClient() as client:
            cfg = parse_ssh_uri(base_path)
            remote_base_path = cfg.pop('remote_file_path')
            client.load_system_host_keys()
            client.connect(**cfg)
            return query_index_from_scp(name, remote_base_path, client, index)

    base_path = Path(base_path)
    if zipfile.is_zipfile(base_path):
        return query_index_from_zipfile(name, base_path, index)
    path = Path(base_path) / "index" / name
    width = int(path.with_suffix('.width').read_text())

    with path.with_suffix('.idx').open("r") as f:
        f.seek(index * (width + 1))
        context = f.read(width)
    return context.rstrip()


@lru_cache(maxsize=4096)
def load_item(id, base_path):
    if isinstance(base_path, str) and base_path.startswith('ssh://'):
        with SSHClient() as client:
            cfg = parse_ssh_uri(base_path)
            remote_base_path = cfg.pop('remote_file_path')
            client.load_system_host_keys()
            client.connect(**cfg)
            buf = load_item_buf_from_scp(id, remote_base_path, client)
    else:
        base_path = Path(base_path)
        if zipfile.is_zipfile(base_path):
            buf = load_item_buf_from_zipfile(id, base_path)
        else:
            path = Path(base_path) / 'items' / id
            with open(path, 'rb') as f:
                buf = f.read()
    item = pickle.loads(lzma.decompress(buf))
    return item


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


#########################################################################
##                            Zipfile support                          ##
#########################################################################


def load_report_from_zipfile(path: str | Path,
                             base_path: str | Path) -> Report | None:
    path = Path(path)
    with zipfile.ZipFile(base_path) as zf:
        path = '/'.join(path.parts)
        with zf.open(f"{base_path.stem}/reports/{path}") as f:
            index = int.from_bytes(f.read(8), 'big')
            report = pickle.loads(lzma.decompress(f.read()))
            report.base_path = base_path
            report.index = index
            return report


def get_heads_from_zipfile(base_path: str | Path) -> Path | None:
    with zipfile.ZipFile(base_path) as zf:
        with zf.open(f"{base_path.stem}/heads") as f:
            heads = pickle.load(f)
    return heads


def query_index_from_zipfile(name: str, base_path: str | Path, index: int):
    with zipfile.ZipFile(base_path) as zf:
        with zf.open(f"{base_path.stem}/index/{name}.width") as f:
            width = int(f.read().decode())
        with zf.open(f"{base_path.stem}/index/{name}.idx") as f:
            f.seek(index * (width + 1))
            context = f.read(width).decode()
    return context.rstrip()


def load_item_buf_from_zipfile(id, base_path):
    with zipfile.ZipFile(base_path) as zf:
        with zf.open(f"{base_path.stem}/items/{id}") as f:
            return f.read()


#########################################################################
##                             SCP support                             ##
#########################################################################


def parse_ssh_uri(uri):
    """
    解析 SSH URI 字符串，返回包含连接参数和路径的字典。
    
    格式：ssh://[{username}[:{password}]@]{host}[:{port}][?key_filename={key_path}][/{remote_file_path}]

    返回示例：
    {
        "username": "user",
        "password": "pass",
        "host": "example.com",
        "port": 22,
        "key_filename": "/path/to/key",
        "remote_file_path": "/data/file.txt"
    }
    """
    pattern = re.compile(
        r"^ssh://"  # 协议头
        r"(?:([^:@/]+))(?::([^@/]+))?@?"  # 用户名和密码（可选）
        r"([^:/?#]+)"  # 主机名（必须）
        r"(?::(\d+))?"  # 端口（可选）
        r"(/?[^?#]*)?"  # 远程路径（可选）
        r"(?:\?([^#]+))?"  # 查询参数（如 key_filename）
        r"$",
        re.IGNORECASE)

    match = pattern.match(uri)
    if not match:
        raise ValueError(f"Invalid SSH URI format: {uri}")

    # 提取分组
    username, password, host, port, path, query = match.groups()

    # 处理查询参数
    key_filename = None
    if query:
        params = parse_qs(query)
        key_filename = params.get("key_filename", [None])[0]  # 取第一个值

    # 清理路径开头的斜杠
    remote_file_path = path

    return {
        "username": username,
        "password": password,
        "hostname": host,
        "port": int(port) if port else 22,  # 默认端口 22
        "key_filename": key_filename,
        "remote_file_path": remote_file_path
    }


def load_report_from_scp(path: str | Path, base_path: Path,
                         client: SSHClient) -> Report:
    try:
        path = Path(path)
        with client.open_sftp() as sftp:
            with sftp.open(str(Path(base_path) / 'reports' / path), 'rb') as f:
                index = int.from_bytes(f.read(8), 'big')
                report = pickle.loads(lzma.decompress(f.read()))
                report.index = index
                return report
    except SSHException:
        raise ValueError(f"Can't load report from {path}")


def get_heads_from_scp(base_path: Path, client: SSHClient) -> Path | None:
    try:
        with client.open_sftp() as sftp:
            with sftp.open(str(Path(base_path) / 'heads'), 'rb') as f:
                heads = pickle.load(f)
        return heads
    except SSHException:
        return None


def query_index_from_scp(name: str, base_path: Path, client: SSHClient,
                         index: int):
    try:
        with client.open_sftp() as sftp:
            s = str(Path(base_path) / 'index' / f'{name}.width')
            with sftp.open(s, 'rb') as f:
                width = int(f.read().decode())
            with sftp.open(str(Path(base_path) / 'index' / f'{name}.idx'),
                           'rb') as f:
                f.seek(index * (width + 1))
                context = f.read(width).decode()
        return context.rstrip()
    except SSHException:
        return None


def load_item_buf_from_scp(id: str, base_path: Path, client: SSHClient):
    try:
        with client.open_sftp() as sftp:
            with sftp.open(str(Path(base_path) / 'items' / str(id)),
                           'rb') as f:
                return f.read()
    except SSHException:
        return None
