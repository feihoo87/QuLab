import pickle
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger


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
    previous: Path | None = None


class Graph:

    def __init__(self):
        self.nodes = {}
        self.heads = set()
        self.roots = set()

    def add_node(self, node: str, deps: list[str]):
        if node not in self.nodes:
            self.nodes[node] = deps
            if not deps:
                self.heads.add(node)
            for dep in deps:
                if dep not in self.nodes:
                    self.nodes[dep] = []
                self.roots.discard(dep)


def random_path(base: Path) -> Path:
    while True:
        s = uuid.uuid4().hex
        path = Path(s[:2]) / s[2:4] / s[4:6] / s[6:]
        if not (base / path).exists():
            return path


def save_result(workflow: str, result: Result, base_path: str | Path):
    logger.debug(
        f'Saving result for "{workflow}", {result.in_spec=}, {result.bad_data=}, {result.fully_calibrated=}'
    )
    base_path = Path(base_path)
    path = random_path(base_path)
    (base_path / 'objects' / path).parent.mkdir(parents=True, exist_ok=True)
    result.previous = get_head(workflow, base_path)
    with open(base_path / 'objects' / path, "wb") as f:
        pickle.dump(result, f)
    set_head(workflow, path, base_path)


def find_result(workflow: str, base_path: str | Path) -> Result | None:
    base_path = Path(base_path)
    path = get_head(workflow, base_path)
    if path is None:
        return None
    with open(base_path / 'objects' / path, "rb") as f:
        return pickle.load(f)


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


def get_graph(base_path: str | Path) -> dict[str, list[str]]:
    base_path = Path(base_path)
    try:
        with open(base_path / "heads", "rb") as f:
            heads = pickle.load(f)
    except:
        heads = {}
    graph = {}
    for workflow, path in heads.items():
        graph[workflow] = []
        while path is not None:
            with open(base_path / 'objects' / path, "rb") as f:
                result = pickle.load(f)
            path = result.previous
            if path is not None:
                graph[workflow].append(path)
    return graph


def update_graph(workflow: str, base_path: str | Path):
    base_path = Path(base_path)
    graph = get_graph(base_path)
    for workflow, deps in graph.items():
        for dep in deps:
            if dep not in graph:
                graph[dep] = []
            if workflow not in graph[dep]:
                graph[dep].append(workflow)
    with open(base_path / "graph", "wb") as f:
        pickle.dump(graph, f)
