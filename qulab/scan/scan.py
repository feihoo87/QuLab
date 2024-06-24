import asyncio
import copy
import inspect
import itertools
import lzma
import os
import pickle
import platform
import re
import subprocess
import sys
import uuid
from concurrent.futures import ProcessPoolExecutor
from graphlib import TopologicalSorter
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable

import dill
import numpy as np
import zmq

from ..sys.rpc.zmq_socket import ZMQContextManager
from .expression import Env, Expression, Symbol
from .optimize import NgOptimizer
from .record import Record
from .server import default_record_port
from .space import Optimizer, OptimizeSpace, Space
from .utils import async_zip, call_function, dump_globals

try:
    from tqdm.notebook import tqdm
except:

    class tqdm():

        def update(self, n):
            pass

        def close(self):
            pass

        def reset(self):
            pass


__process_uuid = uuid.uuid1()
__task_counter = itertools.count()
__notebook_id = None

if os.getenv('QULAB_SERVER'):
    default_server = os.getenv('QULAB_SERVER')
else:
    default_server = f'tcp://127.0.0.1:{default_record_port}'
if os.getenv('QULAB_EXECUTOR'):
    default_executor = os.getenv('QULAB_EXECUTOR')
else:
    default_executor = default_server


def yapf_reformat(cell_text):
    try:
        import isort
        import yapf.yapflib.yapf_api

        fname = f"f{uuid.uuid1().hex}"

        def wrap(source):
            lines = [f"async def {fname}():"]
            for line in source.split('\n'):
                lines.append("    " + line)
            return '\n'.join(lines)

        def unwrap(source):
            lines = []
            for line in source.split('\n'):
                if line.startswith(f"async def {fname}():"):
                    continue
                lines.append(line[4:])
            return '\n'.join(lines)

        cell_text = re.sub('^%', '#%#', cell_text, flags=re.M)
        reformated_text = unwrap(
            yapf.yapflib.yapf_api.FormatCode(wrap(isort.code(cell_text)))[0])
        return re.sub('^#%#', '%', reformated_text, flags=re.M)
    except:
        return cell_text


def get_installed_packages():
    result = subprocess.run([sys.executable, '-m', 'pip', 'freeze'],
                            stdout=subprocess.PIPE,
                            text=True)

    lines = result.stdout.split('\n')
    packages = []
    for line in lines:
        if line:
            packages.append(line)
    return packages


def get_system_info():
    info = {
        'OS': platform.uname()._asdict(),
        'Python': sys.version,
        'PythonExecutable': sys.executable,
        'PythonPath': sys.path,
        'packages': get_installed_packages()
    }
    return info


def current_notebook():
    return __notebook_id


async def create_notebook(name: str, database=default_server, socket=None):
    global __notebook_id

    async with ZMQContextManager(zmq.DEALER, connect=database,
                                 socket=socket) as socket:
        await socket.send_pyobj({'method': 'notebook_create', 'name': name})
        __notebook_id = await socket.recv_pyobj()


async def save_input_cells(notebook_id,
                           input_cells,
                           database=default_server,
                           socket=None):
    async with ZMQContextManager(zmq.DEALER, connect=database,
                                 socket=socket) as socket:
        await socket.send_pyobj({
            'method': 'notebook_extend',
            'notebook_id': notebook_id,
            'input_cells': input_cells
        })
        return await socket.recv_pyobj()


async def create_config(config: dict, database=default_server, socket=None):
    async with ZMQContextManager(zmq.DEALER, connect=database,
                                 socket=socket) as socket:
        buf = lzma.compress(pickle.dumps(config))
        await socket.send_pyobj({'method': 'config_update', 'update': buf})
        return await socket.recv_pyobj()


def task_uuid():
    return uuid.uuid3(__process_uuid, str(next(__task_counter)))


def _get_depends(func: Callable):
    try:
        sig = inspect.signature(func)
    except:
        return []

    args = []
    for name, param in sig.parameters.items():
        if param.kind in [
                param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD,
                param.KEYWORD_ONLY
        ]:
            args.append(name)
        elif param.kind == param.VAR_KEYWORD:
            pass
        elif param.kind == param.VAR_POSITIONAL:
            raise ValueError('not support VAR_POSITIONAL')
    return args


class Promise():
    __slots__ = ['task', 'key', 'attr']

    def __init__(self, task, key=None, attr=None):
        self.task = task
        self.key = key
        self.attr = attr

    def __await__(self):

        async def _getitem(task, key):
            return (await task)[key]

        async def _getattr(task, attr):
            return getattr(await task, attr)

        if self.key is not None:
            return _getitem(self.task, self.key).__await__()
        elif self.attr is not None:
            return _getattr(self.task, self.attr).__await__()
        else:
            return self.task.__await__()

    def __getitem__(self, key):
        return Promise(self.task, key, None)

    def __getattr__(self, attr):
        return Promise(self.task, None, attr)


def _run_function_in_process(buf):
    func, args, kwds = dill.loads(buf)
    return func(*args, **kwds)


class Scan():

    def __new__(cls, *args, mixin=None, **kwds):
        if mixin is None:
            return super().__new__(cls)
        for k in dir(mixin):
            if not hasattr(cls, k):
                try:
                    setattr(cls, k, getattr(mixin, k))
                except:
                    pass
        return super().__new__(cls)

    def __init__(self,
                 app: str = 'task',
                 tags: tuple[str] = (),
                 database: str | Path
                 | None = default_server,
                 dump_globals: bool = False,
                 max_workers: int = 4,
                 max_promise: int = 100,
                 max_message: int = 1000,
                 config: dict | None = None,
                 mixin=None):
        self.id = task_uuid()
        self.record = None
        self.config = {} if config is None else copy.deepcopy(config)
        self.description = {
            'app': app,
            'tags': tags,
            'config': None,
            'loops': {},
            'intrinsic_loops': {},
            'consts': {},
            'functions': {},
            'getters': {},
            'setters': {},
            'optimizers': {},
            'namespace': {} if dump_globals else None,
            'actions': {},
            'dependents': {},
            'order': {},
            'axis': {},
            'independent_variables': set(),
            'filters': {},
            'total': {},
            'database': database,
            'hiden': ['self', 'config', r'^__.*', r'.*__$'],
            'entry': {
                'system': get_system_info(),
                'env': {},
                'shell': '',
                'cmds': [],
                'scripts': []
            },
        }
        self._current_level = 0
        self._variables = {}
        self._main_task = None
        self._sock = None
        self._sem = asyncio.Semaphore(max_promise + 1)
        self._bar: dict[int, tqdm] = {}
        self._hide_pattern_re = re.compile('|'.join(self.description['hiden']))
        self._msg_queue = asyncio.Queue(max_message)
        self._prm_queue = asyncio.Queue()
        self._single_step = True
        self._max_workers = max_workers
        self._max_promise = max_promise
        self._max_message = max_message
        self._executors = ProcessPoolExecutor(max_workers=max_workers)

    def __del__(self):
        try:
            self._main_task.cancel()
        except:
            pass

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        del state['record']
        del state['_sock']
        del state['_main_task']
        del state['_bar']
        del state['_msg_queue']
        del state['_prm_queue']
        del state['_sem']
        del state['_executors']
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)
        self.record = None
        self._sock = None
        self._main_task = None
        self._bar = {}
        self._prm_queue = asyncio.Queue()
        self._msg_queue = asyncio.Queue(self._max_message)
        self._sem = asyncio.Semaphore(self._max_promise + 1)
        self._executors = ProcessPoolExecutor(max_workers=self._max_workers)
        for opt in self.description['optimizers'].values():
            opt.scanner = self

    def __del__(self):
        try:
            self._main_task.cancel()
        except:
            pass
        try:
            self._executors.shutdown()
        except:
            pass

    @property
    def current_level(self):
        return self._current_level

    @property
    def variables(self) -> dict[str, Any]:
        return self._variables

    async def _emit(self, current_level, step, position, variables: dict[str,
                                                                         Any]):
        for key, value in list(variables.items()):
            if key.startswith('*') or ',' in key:
                await _unpack(key, variables)
            elif inspect.isawaitable(value) and not self.hiden(key):
                variables[key] = await value
        if self._sock is not None:
            await self._sock.send_pyobj({
                'task': self.id,
                'method': 'record_append',
                'record_id': self.record.id,
                'level': current_level,
                'step': step,
                'position': position,
                'variables': {
                    k: v
                    for k, v in variables.items() if not self.hiden(k)
                }
            })
        else:
            self.record.append(current_level, step, position, {
                k: v
                for k, v in variables.items() if not self.hiden(k)
            })

    async def emit(self, current_level, step, position, variables: dict[str,
                                                                        Any]):
        await self._msg_queue.put(
            self._emit(current_level, step, position, variables.copy()))

    def hide(self, name: str):
        self.description['hiden'].append(name)
        self._hide_pattern_re = re.compile('|'.join(self.description['hiden']))

    def hiden(self, name: str) -> bool:
        return bool(self._hide_pattern_re.match(name)) or name.startswith(
            '*') or ',' in name

    async def _filter(self, variables: dict[str, Any], level: int = 0):
        try:
            return all(await asyncio.gather(*[
                call_function(fun, variables) for fun in itertools.chain(
                    self.description['filters'].get(level, []),
                    self.description['filters'].get(-1, []))
            ]))
        except:
            return True

    async def create_record(self):
        if self._sock is not None:
            await self._sock.send_pyobj({
                'task':
                self.id,
                'method':
                'record_create',
                'description':
                dill.dumps(self.description)
            })

            record_id = await self._sock.recv_pyobj()
            return Record(record_id, self.description['database'],
                          self.description)
        return Record(None, self.description['database'], self.description)

    def get(self, name: str):
        if name in self.description['consts']:
            return self.description['consts'][name]
        else:
            try:
                return self._query_config(name)
            except:
                return Symbol(name)

    def _add_search_space(self, name: str, level: int, space):
        if level not in self.description['loops']:
            self.description['loops'][level] = []
        self.description['loops'][level].append((name, space))

    def add_depends(self, name: str, depends: list[str]):
        if isinstance(depends, str):
            depends = [depends]
        if 'self' in depends:
            depends.append('config')
        if name not in self.description['dependents']:
            self.description['dependents'][name] = set()
        self.description['dependents'][name].update(depends)

    def add_filter(self, func: Callable, level: int = -1):
        """
        Add a filter function to the scan.

        Args:
            func: A callable object or an instance of Expression.
            level: The level of the scan to add the filter. -1 means any level.
        """
        if level not in self.description['filters']:
            self.description['filters'][level] = []
        self.description['filters'][level].append(func)

    def set(self,
            name: str,
            value,
            depends: Iterable[str] | None = None,
            setter: Callable | None = None):
        try:
            dill.dumps(value)
        except:
            raise ValueError('value is not serializable.')
        if isinstance(value, Expression):
            self.add_depends(name, value.symbols())
            self.description['functions'][name] = value
        elif callable(value):
            if depends:
                self.add_depends(name, depends)
                s = ','.join(depends)
                self.description['functions'][f'_tmp_{name}'] = value
                self.description['functions'][name] = eval(
                    f"lambda self, {s}: self.description['functions']['_tmp_{name}']({s})"
                )
            else:
                self.add_depends(name, _get_depends(value))
                self.description['functions'][name] = value
        else:
            try:
                value = Space.fromarray(value)
            except:
                pass
            self.description['consts'][name] = value

        if '.' in name:
            self.add_depends('config', [name])

        if ',' in name:
            for key in name.split(','):
                if not key.startswith('*'):
                    self.add_depends(key, [name])
        if setter:
            self.description['setters'][name] = setter

    def search(self,
               name: str,
               space: Iterable | Expression | Callable | OptimizeSpace,
               level: int | None = None,
               setter: Callable | None = None,
               intrinsic: bool = False):
        if level is not None:
            if not intrinsic:
                assert level >= 0, 'level must be greater than or equal to 0.'
        if intrinsic:
            assert isinstance(space, (np.ndarray, list, tuple, range, Space)), \
                'space must be an instance of np.ndarray, list, tuple, range or Space.'
            self.description['intrinsic_loops'][name] = level
            self.set(name, space)
        elif isinstance(space, OptimizeSpace):
            space.name = name
            space.optimizer.dimensions[name] = space.space
            if space.suggestion:
                space.optimizer.suggestion[name] = space.suggestion
            self._add_search_space(name, space.optimizer.level, space)
            self.add_depends(space.optimizer.name, [name])
        else:
            if level is None:
                raise ValueError('level must be provided.')
            try:
                space = Space.fromarray(space)
            except:
                pass
            self._add_search_space(name, level, space)
            if isinstance(space, Expression) or callable(space):
                self.add_depends(name, space.symbols())
        if setter:
            self.description['setters'][name] = setter
        if '.' in name:
            self.add_depends('config', [name])

    def trace(self,
              name: str,
              depends: list[str],
              getter: Callable | None = None):
        self.add_depends(name, depends)
        if getter:
            self.description['getters'][name] = getter

    def minimize(self,
                 name: str,
                 level: int,
                 method=NgOptimizer,
                 maxiter=100,
                 getter: Callable | None = None,
                 **kwds) -> Optimizer:
        assert level >= 0, 'level must be greater than or equal to 0.'
        opt = Optimizer(self,
                        name,
                        level,
                        method,
                        maxiter,
                        minimize=True,
                        **kwds)
        self.description['optimizers'][name] = opt
        if getter:
            self.description['getters'][name] = getter
        return opt

    def maximize(self,
                 name: str,
                 level: int,
                 method=NgOptimizer,
                 maxiter=100,
                 getter: Callable | None = None,
                 **kwds) -> Optimizer:
        assert level >= 0, 'level must be greater than or equal to 0.'
        opt = Optimizer(self,
                        name,
                        level,
                        method,
                        maxiter,
                        minimize=False,
                        **kwds)
        self.description['optimizers'][name] = opt
        if getter:
            self.description['getters'][name] = getter
        return opt

    def _synchronize_config(self):
        for key, value in self.variables.items():
            if '.' in key:
                d = self.config
                ks = key.split('.')
                if not ks:
                    continue
                for k in ks[:-1]:
                    if k in d:
                        d = d[k]
                    else:
                        d[k] = {}
                        d = d[k]
                d[ks[-1]] = value
        return self.config

    def _query_config(self, key):
        d = self.config
        for k in key.split('.'):
            d = d[k]
        return d

    async def _update_progress(self):
        while True:
            task = await self._prm_queue.get()
            await task
            self._prm_queue.task_done()

    async def _send_msg(self):
        while True:
            task = await self._msg_queue.get()
            await task
            self._msg_queue.task_done()

    async def run(self):
        assymbly(self.description)
        if isinstance(
                self.description['database'],
                str) and self.description['database'].startswith("tcp://"):
            async with ZMQContextManager(zmq.DEALER,
                                         connect=self.description['database'],
                                         socket=self._sock) as socket:
                self._sock = socket
                if self.config:
                    self.description['config'] = await create_config(
                        self.config, self.description['database'], self._sock)
                if current_notebook() is None:
                    await create_notebook('untitle',
                                          self.description['database'],
                                          self._sock)
                cell_id = await save_input_cells(
                    current_notebook(), self.description['entry']['scripts'],
                    self.description['database'], self._sock)
                self.description['entry']['scripts'] = cell_id
                await self._run()
        else:
            if self.config:
                self.description['config'] = copy.deepcopy(self.config)
            await self._run()

    async def _run(self):
        send_msg_task = asyncio.create_task(self._send_msg())
        update_progress_task = asyncio.create_task(self._update_progress())

        self._variables = {'self': self, 'config': self.config}

        consts = {}
        for k, v in self.description['consts'].items():
            if isinstance(v, Space):
                consts[k] = v.toarray()
            else:
                consts[k] = v

        await update_variables(self._variables, consts,
                               self.description['setters'])
        for level, total in self.description['total'].items():
            if total == np.inf:
                total = None
            self._bar[level] = tqdm(total=total)

        updates = await call_many_functions(
            self.description['order'].get(-1, []),
            self.description['functions'], self.variables)
        await update_variables(self.variables, updates,
                               self.description['setters'])

        self.record = await self.create_record()
        await self.work()
        for level, bar in self._bar.items():
            bar.close()

        if self._single_step:
            self.variables.update(await call_many_functions(
                self.description['order'].get(-1, []),
                self.description['getters'], self.variables))

            await self.emit(0, 0, 0, self.variables)
            await self.emit(-1, 0, 0, {})

        await self._prm_queue.join()
        update_progress_task.cancel()
        await self._msg_queue.join()
        send_msg_task.cancel()
        return self.variables

    async def done(self):
        if self._main_task is not None:
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass

    def finished(self):
        return self._main_task.done()

    def start(self):
        import asyncio
        self._main_task = asyncio.create_task(self.run())

    async def submit(self, server=default_executor):
        assymbly(self.description)
        async with ZMQContextManager(zmq.DEALER,
                                     connect=server,
                                     socket=self._sock) as socket:
            await socket.send_pyobj({
                'method': 'task_submit',
                'description': dill.dumps(self.description)
            })
            self.id = await socket.recv_pyobj()
            await socket.send_pyobj({
                'method': 'task_get_record_id',
                'id': self.id
            })
            record_id = await socket.recv_pyobj()
            self.record = Record(record_id, self.description['database'],
                                 self.description)

    def cancel(self):
        if self._main_task is not None:
            self._main_task.cancel()

    async def _reset_progress_bar(self, level):
        if level in self._bar:
            self._bar[level].reset()

    async def _update_progress_bar(self, level, n: int):
        if level in self._bar:
            self._bar[level].update(n)

    async def iter(self, **kwds):
        if self.current_level >= len(self.description['loops']):
            return
        step = 0
        position = 0
        self._prm_queue.put_nowait(self._reset_progress_bar(
            self.current_level))
        async for variables in _iter_level(
                self.variables,
                self.description['loops'].get(self.current_level, []),
                self.description['order'].get(self.current_level, []),
                self.description['functions']
                | {'config': self._synchronize_config},
                self.description['optimizers'], self.description['setters'],
                self.description['getters']):
            self._current_level += 1
            if await self._filter(variables, self.current_level - 1):
                yield variables
                self._single_step = False
                await self.emit(self.current_level - 1, step, position,
                                variables)
                step += 1
            position += 1
            self._current_level -= 1
            self._prm_queue.put_nowait(
                self._update_progress_bar(self.current_level, 1))
        if self.current_level == 0:
            await self.emit(self.current_level - 1, 0, 0, {})
            for name, value in self.variables.items():
                if inspect.isawaitable(value):
                    self.variables[name] = await value
            await self._prm_queue.join()

    async def work(self, **kwds):
        if self.current_level in self.description['actions']:
            action = self.description['actions'][self.current_level]
            coro = action(self, **kwds)
            if inspect.isawaitable(coro):
                await coro
        else:
            async for variables in self.iter(**kwds):
                await self.do_something(**kwds)

    async def do_something(self, **kwds):
        await self.work(**kwds)

    def mount(self, action: Callable, level: int):
        """
        Mount a action to the scan.

        Args:
            action: A callable object.
            level: The level of the scan to mount the action.
        """
        self.description['actions'][level] = action

    async def promise(self, awaitable: Awaitable | Callable, *args,
                      **kwds) -> Promise:
        """
        Promise to calculate asynchronous function and return the result in future.

        Args:
            awaitable: An awaitable object.

        Returns:
            Promise: A promise object.
        """
        if inspect.isawaitable(awaitable):
            async with self._sem:
                task = asyncio.create_task(self._await(awaitable))
                self._prm_queue.put_nowait(task)
                return Promise(task)
        elif inspect.iscoroutinefunction(awaitable):
            return await self.promise(awaitable(*args, **kwds))
        elif callable(awaitable):
            try:
                buf = dill.dumps((awaitable, args, kwds))
                task = asyncio.get_running_loop().run_in_executor(
                    self._executors, _run_function_in_process, buf)
                self._prm_queue.put_nowait(task)
                return Promise(task)
            except:
                return awaitable(*args, **kwds)
        else:
            return awaitable

    async def _await(self, awaitable: Awaitable):
        async with self._sem:
            return await awaitable


def assymbly(description):
    import __main__
    from IPython import get_ipython

    if isinstance(description['namespace'], dict):
        description['namespace'] = dump_globals()

    ipy = get_ipython()
    if ipy is not None:
        description['entry']['shell'] = 'ipython'
        description['entry']['scripts'] = [
            yapf_reformat(cell_text) for cell_text in ipy.user_ns['In']
        ]
    else:
        try:
            description['entry']['shell'] = 'shell'
            description['entry']['cmds'] = [
                sys.executable, __main__.__file__, *sys.argv[1:]
            ]
            description['entry']['scripts'] = []
            try:
                with open(__main__.__file__) as f:
                    description['entry']['scripts'].append(f.read())
            except:
                pass
        except:
            pass

    description['entry']['env'] = {k: v for k, v in os.environ.items()}

    mapping = {
        label: level
        for level, label in enumerate(
            sorted(
                set(description['loops'].keys())
                | {k
                   for k in description['actions'].keys() if k >= 0}))
    }

    if -1 in description['actions']:
        mapping[-1] = max(mapping.values()) + 1

    levels = sorted(mapping.values())
    for k in description['actions'].keys():
        if k < -1:
            mapping[k] = levels[k]

    description['loops'] = dict(
        sorted([(mapping[k], v) for k, v in description['loops'].items()]))
    description['actions'] = {
        mapping[k]: v
        for k, v in description['actions'].items()
    }

    for level, loops in description['loops'].items():
        description['total'][level] = np.inf
        for name, space in loops:
            try:
                description['total'][level] = min(description['total'][level],
                                                  len(space))
            except:
                pass

    dependents = copy.deepcopy(description['dependents'])

    for level in levels:
        range_list = description['loops'].get(level, [])
        if level > 0:
            if f'#__loop_{level}' not in description['dependents']:
                dependents[f'#__loop_{level}'] = set()
            dependents[f'#__loop_{level}'].add(f'#__loop_{level-1}')
        for name, _ in range_list:
            if name not in description['dependents']:
                dependents[name] = set()
            dependents[name].add(f'#__loop_{level}')

    def _get_all_depends(key, graph):
        ret = set()
        if key not in graph:
            return ret

        for e in graph[key]:
            ret.update(_get_all_depends(e, graph))
        ret.update(graph[key])
        return ret

    full_depends = {}
    for key in dependents:
        full_depends[key] = _get_all_depends(key, dependents)

    levels = {}
    passed = set()
    all_keys = set(description['consts'].keys())
    for key in dependents:
        all_keys.add(key)
        all_keys.update(dependents[key])
    for level in reversed(description['loops'].keys()):
        tag = f'#__loop_{level}'
        for key, deps in full_depends.items():
            all_keys.update(deps)
            all_keys.add(key)
            if key.startswith('#__loop_'):
                continue
            if tag in deps:
                if level not in levels:
                    levels[level] = set()
                if key not in passed:
                    passed.add(key)
                    levels[level].add(key)
    levels[-1] = {
        key
        for key in all_keys - passed if not key.startswith('#__loop_')
    }

    order = []
    ts = TopologicalSorter(dependents)
    ts.prepare()
    while ts.is_active():
        ready = ts.get_ready()
        order.append(ready)
        for k in ready:
            ts.done(k)

    description['order'] = {}

    for level in sorted(levels):
        keys = set(levels[level])
        description['order'][level] = []
        for ready in order:
            ready = list(keys & set(ready))
            if ready:
                description['order'][level].append(ready)
                keys -= set(ready)

    axis = {}
    independent_variables = set(description['intrinsic_loops'].keys())

    for name in description['consts']:
        axis[name] = ()
    for level, range_list in description['loops'].items():
        for name, iterable in range_list:
            if isinstance(iterable, OptimizeSpace):
                axis[name] = tuple(range(level + 1))
                continue
            elif isinstance(iterable, (np.ndarray, list, tuple, range, Space)):
                independent_variables.add(name)
            axis[name] = (level, )

    for level, group in description['order'].items():
        for names in group:
            for name in names:
                if name not in description['dependents']:
                    if name not in axis:
                        axis[name] = (level, )
                else:
                    d = set()
                    for n in description['dependents'][name]:
                        d.update(axis[n])
                    if name not in axis:
                        axis[name] = tuple(sorted(d))
                    else:
                        axis[name] = tuple(sorted(set(axis[name]) | d))
    description['axis'] = {
        k: tuple([x for x in v if x >= 0])
        for k, v in axis.items()
    }
    description['independent_variables'] = independent_variables

    return description


async def update_variables(variables: dict[str, Any], updates: dict[str, Any],
                           setters: dict[str, Callable]):
    coros = []
    for name, value in updates.items():
        if name in setters:
            coro = setters[name](value)
            if inspect.isawaitable(coro):
                coros.append(coro)
        variables[name] = value
    if coros:
        await asyncio.gather(*coros)


async def _iter_level(variables,
                      iters: list[tuple[str, Iterable | Expression | Callable
                                        | OptimizeSpace]],
                      order: list[list[str]],
                      functions: dict[str, Callable | Expression],
                      optimizers: dict[str, Optimizer],
                      setters: dict[str, Callable] = {},
                      getters: dict[str, Callable] = {}):
    iters_d = {}
    env = Env()
    env.variables = variables
    opts = {}

    for name, iter in iters:
        if isinstance(iter, OptimizeSpace):
            if iter.optimizer.name not in opts:
                opts[iter.optimizer.name] = iter.optimizer.create()
        elif isinstance(iter, Expression):
            iters_d[name] = iter.eval(env)
        elif isinstance(iter, Space):
            iters_d[name] = iter.toarray()
        elif callable(iter):
            iters_d[name] = await call_function(iter, variables)
        else:
            iters_d[name] = iter

    maxiter = 0xffffffff
    for name, opt in opts.items():
        opt_cfg = optimizers[name]
        maxiter = min(maxiter, opt_cfg.maxiter)

    async for args in async_zip(*iters_d.values(), range(maxiter)):
        await update_variables(variables, dict(zip(iters_d.keys(), args[:-1])),
                               setters)
        for name, opt in opts.items():
            args = opt.ask()
            opt_cfg = optimizers[name]
            await update_variables(variables, {
                n: v
                for n, v in zip(opt_cfg.dimensions.keys(), args)
            }, setters)

        await update_variables(
            variables, await call_many_functions(order, functions, variables),
            setters)

        yield variables

        variables.update(await call_many_functions(order, getters, variables))

        if opts:
            for key in list(variables.keys()):
                if key.startswith('*') or ',' in key:
                    await _unpack(key, variables)

        for name, opt in opts.items():
            opt_cfg = optimizers[name]
            args = [variables[n] for n in opt_cfg.dimensions.keys()]

            if name not in variables:
                raise ValueError(f'{name} not in variables.')
            fun = variables[name]
            if inspect.isawaitable(fun):
                fun = await fun
            if opt_cfg.minimize:
                opt.tell(args, fun)
            else:
                opt.tell(args, -fun)

    for name, opt in opts.items():
        opt_cfg = optimizers[name]
        result = opt.get_result()
        await update_variables(
            variables, {
                name: value
                for name, value in zip(opt_cfg.dimensions.keys(), result.x)
            }, setters)
        variables[name] = result.fun
    if opts:
        yield variables


async def call_many_functions(order: list[list[str]],
                              functions: dict[str, Callable],
                              variables: dict[str, Any]) -> dict[str, Any]:
    ret = {}
    for group in order:
        waited = []
        coros = []
        for name in group:
            if name in functions:
                waited.append(name)
                coros.append(call_function(functions[name], variables | ret))
        if coros:
            results = await asyncio.gather(*coros)
            ret.update(dict(zip(waited, results)))
    return ret


async def _unpack(key, variables):
    x = variables[key]
    if inspect.isawaitable(x):
        x = await x
    if key.startswith('**'):
        assert isinstance(
            x, dict), f"Should promise a dict for `**` symbol. {key}"
        if "{key}" in key:
            for k, v in x.items():
                variables[key[2:].format(key=k)] = v
        else:
            variables.update(x)
    elif key.startswith('*'):
        assert isinstance(
            x, (list, tuple,
                np.ndarray)), f"Should promise a list for `*` symbol. {key}"
        for i, v in enumerate(x):
            k = key[1:].format(i=i)
            variables[k] = v
    elif ',' in key:
        keys1, keys2 = [], []
        args = None
        for k in key.split(','):
            if k.startswith('*'):
                if args is None:
                    args = k
                else:
                    raise ValueError(f'Only one `*` symbol is allowed. {key}')
            elif args is None:
                keys1.append(k)
            else:
                keys2.append(k)
        assert isinstance(
            x,
            (list, tuple,
             np.ndarray)), f"Should promise a list for multiple symbols. {key}"
        if args is None:
            assert len(keys1) == len(
                x), f"Length of keys and values should be equal. {key}"
            for k, v in zip(keys1, x):
                variables[k] = v
        else:
            assert len(keys1) + len(keys2) <= len(
                x), f"Too many values for unpacking. {key}"
            for k, v in zip(keys1, x[:len(keys1)]):
                variables[k] = v
            end = -len(keys2) if keys2 else None
            for i, v in enumerate(x[len(keys1):end]):
                k = args[1:].format(i=i)
                variables[k] = v
            if keys2:
                for k, v in zip(keys2, x[end:]):
                    variables[k] = v
    else:
        return
    del variables[key]
