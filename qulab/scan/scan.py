import asyncio
import datetime
import inspect
import itertools
import os
import re
import sys
import uuid
from graphlib import TopologicalSorter
from pathlib import Path
from types import MethodType
from typing import Any, Awaitable, Callable, Iterable, Type

import dill
import numpy as np
import skopt
import zmq
from skopt.space import Categorical, Integer, Real
from tqdm.notebook import tqdm

from ..sys.rpc.zmq_socket import ZMQContextManager
from .expression import Env, Expression, Symbol
from .optimize import NgOptimizer
from .recorder import Record
from .utils import async_zip, call_function

__process_uuid = uuid.uuid1()
__task_counter = itertools.count()


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


class OptimizeSpace():

    def __init__(self, optimizer: 'Optimizer', space):
        self.optimizer = optimizer
        self.space = space
        self.name = None

    def __len__(self):
        return self.optimizer.maxiter


class Optimizer():

    def __init__(self,
                 scanner: 'Scan',
                 name: str,
                 level: int,
                 method: str | Type = skopt.Optimizer,
                 maxiter: int = 1000,
                 minimize: bool = True,
                 **kwds):
        self.scanner = scanner
        self.method = method
        self.maxiter = maxiter
        self.dimensions = {}
        self.name = name
        self.level = level
        self.kwds = kwds
        self.minimize = minimize

    def create(self):
        return self.method(list(self.dimensions.values()), **self.kwds)

    def Categorical(self,
                    categories,
                    prior=None,
                    transform=None,
                    name=None) -> OptimizeSpace:
        return OptimizeSpace(self,
                             Categorical(categories, prior, transform, name))

    def Integer(self,
                low,
                high,
                prior="uniform",
                base=10,
                transform=None,
                name=None,
                dtype=np.int64) -> OptimizeSpace:
        return OptimizeSpace(
            self, Integer(low, high, prior, base, transform, name, dtype))

    def Real(self,
             low,
             high,
             prior="uniform",
             base=10,
             transform=None,
             name=None,
             dtype=float) -> OptimizeSpace:
        return OptimizeSpace(
            self, Real(low, high, prior, base, transform, name, dtype))

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        del state['scanner']
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)
        self.scanner = None


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
                 database: str | Path | None = 'tcp://127.0.0.1:6789',
                 mixin=None):
        self.id = task_uuid()
        self.record = None
        self.namespace = {}
        self.description = {
            'app': app,
            'tags': tags,
            'loops': {},
            'consts': {},
            'functions': {},
            'optimizers': {},
            'actions': {},
            'dependents': {},
            'order': {},
            'filters': {},
            'total': {}
        }
        self._current_level = 0
        self.variables = {}
        self._task = None
        self.sock = None
        self.database = database
        self._sem = asyncio.Semaphore(100)
        self._bar: dict[int, tqdm] = {}
        self._hide_patterns = [r'^__.*', r'.*__$']
        self._hide_pattern_re = re.compile('|'.join(self._hide_patterns))
        self._task_queue = asyncio.Queue()

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        del state['record']
        del state['sock']
        del state['_task']
        del state['_sem']
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)
        self.record = None
        self.sock = None
        self._task = None
        self._sem = asyncio.Semaphore(100)
        for opt in self.description['optimizers'].values():
            opt.scanner = self

    @property
    def current_level(self):
        return self._current_level

    async def emit(self, current_level, step, position, variables: dict[str,
                                                                        Any]):
        for key, value in list(variables.items()):
            if inspect.isawaitable(value) and not self.hiden(key):
                variables[key] = await value
        if self.sock is not None:
            await self.sock.send_pyobj({
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
            self.record.append(current_level, step, position, variables)

    def hide(self, name: str):
        self._hide_patterns.append(name)
        self._hide_pattern_re = re.compile('|'.join(self._hide_patterns))

    def hiden(self, name: str) -> bool:
        return bool(self._hide_pattern_re.match(name))

    async def _filter(self, variables: dict[str, Any], level: int = 0):
        try:
            return all([
                await call_function(fun, variables) for fun in itertools.chain(
                    self.description['filters'].get(level, []),
                    self.description['filters'].get(-1, []))
            ])
        except:
            return True

    async def create_record(self):
        import __main__
        from IPython import get_ipython

        ipy = get_ipython()
        if ipy is not None:
            scripts = ('ipython', ipy.user_ns['In'])
        else:
            try:
                scripts = ('shell',
                           [sys.executable, __main__.__file__, *sys.argv[1:]])
            except:
                scripts = ('', [])

        self.description['ctime'] = datetime.datetime.now()
        self.description['scripts'] = scripts
        self.description['env'] = {k: v for k, v in os.environ.items()}
        if self.sock is not None:
            await self.sock.send_pyobj({
                'task':
                self.id,
                'method':
                'record_create',
                'description':
                dill.dumps(self.description)
            })

            record_id = await self.sock.recv_pyobj()
            return Record(record_id, self.database, self.description)
        return Record(None, self.database, self.description)

    def get(self, name: str):
        if name in self.description['consts']:
            return self.description['consts'][name]
        elif name in self.namespace:
            return self.namespace.get(name)
        else:
            return Symbol(name)

    def _add_loop_var(self, name: str, level: int, range):
        if level not in self.description['loops']:
            self.description['loops'][level] = []
        self.description['loops'][level].append((name, range))

    def add_depends(self, name: str, depends: list[str]):
        if isinstance(depends, str):
            depends = [depends]
        if name not in self.description['dependents']:
            self.description['dependents'][name] = set()
        self.description['dependents'][name].update(depends)

    def add_filter(self, func: Callable, level: int):
        """
        Add a filter function to the scan.

        Args:
            func: A callable object or an instance of Expression.
            level: The level of the scan to add the filter. -1 means any level.
        """
        if level not in self.description['filters']:
            self.description['filters'][level] = []
        self.description['filters'][level].append(func)

    def set(self, name: str, value):
        if isinstance(value, Expression):
            self.add_depends(name, value.symbols())
            self.description['functions'][name] = value
        elif callable(value):
            self.add_depends(name, _get_depends(value))
            self.description['functions'][name] = value
        else:
            self.description['consts'][name] = value

    def search(self, name: str, range, level: int | None = None):
        if level is not None:
            assert level >= 0, 'level must be greater than or equal to 0.'
        if isinstance(range, OptimizeSpace):
            range.name = name
            range.optimizer.dimensions[name] = range.space
            self._add_loop_var(name, range.optimizer.level, range)
            self.add_depends(range.optimizer.name, [name])
        else:
            if level is None:
                raise ValueError('level must be provided.')
            self._add_loop_var(name, level, range)
            if isinstance(range, Expression) or callable(range):
                self.add_depends(name, range.symbols())

    def minimize(self,
                 name: str,
                 level: int,
                 method=NgOptimizer,
                 maxiter=100,
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
        return opt

    def maximize(self,
                 name: str,
                 level: int,
                 method=NgOptimizer,
                 maxiter=100,
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
        return opt

    async def _update_progress(self):
        while True:
            task = await self._task_queue.get()
            if isinstance(task, asyncio.Event):
                task.set()
            elif inspect.isawaitable(task):
                await task

    async def _run(self):
        assymbly(self.description)
        task = asyncio.create_task(self._update_progress())
        self.variables = self.description['consts'].copy()
        for level, total in self.description['total'].items():
            if total == np.inf:
                total = None
            self._bar[level] = tqdm(total=total)
        for group in self.description['order'].get(-1, []):
            for name in group:
                if name in self.description['functions']:
                    self.variables[name] = await call_function(
                        self.description['functions'][name], self.variables)
        if isinstance(self.database,
                      str) and self.database.startswith("tcp://"):
            async with ZMQContextManager(zmq.DEALER,
                                         connect=self.database) as socket:
                self.sock = socket
                self.record = await self.create_record()
                await self.work()
        else:
            self.record = await self.create_record()
            await self.work()
        for level, bar in self._bar.items():
            bar.close()
        task.cancel()
        return self.variables

    async def done(self):
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def start(self):
        import asyncio
        self._task = asyncio.create_task(self._run())

    def cancel(self):
        if self._task is not None:
            self._task.cancel()

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
        task = None
        self._task_queue.put_nowait(
            self._reset_progress_bar(self.current_level))
        async for variables in _iter_level(
                self.variables,
                self.description['loops'].get(self.current_level, []),
                self.description['order'].get(self.current_level, []),
                self.description['functions'], self.description['optimizers']):
            self._current_level += 1
            if await self._filter(variables, self.current_level - 1):
                yield variables
                task = asyncio.create_task(
                    self.emit(self.current_level - 1, step, position,
                              variables.copy()))
                step += 1
            position += 1
            self._current_level -= 1
            self._task_queue.put_nowait(
                self._update_progress_bar(self.current_level, 1))
        if task is not None:
            await task
        if self.current_level == 0:
            await self.emit(self.current_level - 1, 0, 0, {})
            for name, value in self.variables.items():
                if inspect.isawaitable(value):
                    self.variables[name] = await value
            while not self._task_queue.empty():
                task = self._task_queue.get_nowait()
                if inspect.isawaitable(task):
                    await task

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

    async def promise(self, awaitable: Awaitable) -> Promise:
        """
        Promise to calculate asynchronous function and return the result in future.

        Args:
            awaitable: An awaitable object.

        Returns:
            Promise: A promise object.
        """
        async with self._sem:
            task = asyncio.create_task(self._await(awaitable))
            self._task_queue.put_nowait(task)
            return Promise(task)

    async def _await(self, awaitable: Awaitable):
        async with self._sem:
            return await awaitable


def assymbly(description):
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

    dependents = description['dependents'].copy()

    for level in levels:
        range_list = description['loops'].get(level, [])
        if level > 0:
            if f'#__loop_{level}' not in description['dependents']:
                dependents[f'#__loop_{level}'] = []
            dependents[f'#__loop_{level}'].append(f'#__loop_{level-1}')
        for name, _ in range_list:
            if name not in description['dependents']:
                dependents[name] = []
            dependents[name].append(f'#__loop_{level}')

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
    all_keys = set()
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
    return description


async def _iter_level(variables,
                      iters: list[tuple[str, Iterable | Expression | Callable
                                        | OptimizeSpace]],
                      order: list[list[str]],
                      functions: dict[str, Callable | Expression],
                      optimizers: dict[str, Optimizer]):
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
        elif callable(iter):
            iters_d[name] = await call_function(iter, variables)
        else:
            iters_d[name] = iter

    maxiter = 0xffffffff
    for name, opt in opts.items():
        opt_cfg = optimizers[name]
        maxiter = min(maxiter, opt_cfg.maxiter)

    async for args in async_zip(*iters_d.values(), range(maxiter)):
        variables.update(dict(zip(iters_d.keys(), args[:-1])))
        for name, opt in opts.items():
            args = opt.ask()
            opt_cfg = optimizers[name]
            variables.update({
                n: v
                for n, v in zip(opt_cfg.dimensions.keys(), args)
            })

        for group in order:
            for name in group:
                if name in functions:
                    variables[name] = await call_function(
                        functions[name], variables)

        yield variables

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
        variables.update({
            n: v
            for n, v in zip(opt_cfg.dimensions.keys(), result.x)
        })
        variables[name] = result.fun
    if opts:
        yield variables
