
import inspect
import logging
import warnings
from abc import ABC, abstractclassmethod
from concurrent.futures import Executor, Future
from dataclasses import dataclass, field
from graphlib import TopologicalSorter
from itertools import chain, count

from queue import Empty, Queue
from typing import Any, Callable, Iterable, Sequence, Type

log = logging.getLogger(__name__)
log.setLevel(logging.ERROR)


class BaseOptimizer(ABC):

    @abstractclassmethod
    def ask(self) -> tuple:
        pass

    @abstractclassmethod
    def tell(self, suggested: Sequence, value: Any):
        pass

    @abstractclassmethod
    def get_result(self):
        pass


@dataclass
class OptimizerConfig():
    cls: Type[BaseOptimizer]
    dimensions: list = field(default_factory=list)
    args: tuple = ()
    kwds: dict = field(default_factory=dict)
    max_iters: int = 100


class FeedbackPipe():
    __slots__ = (
        'keys',
        '_queue',
    )

    def __init__(self, keys):
        self.keys = keys
        self._queue = Queue()

    def __iter__(self):
        while True:
            try:
                yield self._queue.get_nowait()
            except Empty:
                break

    def __call__(self):
        return self.__iter__()

    def send(self, obj):
        self._queue.put(obj)

    def __repr__(self):
        if not isinstance(self.keys, tuple):
            return f'FeedbackProxy({repr(self.keys)})'
        else:
            return f'FeedbackProxy{self.keys}'


class FeedbackProxy():

    def feedback(self, keywords, obj, suggested=None):
        if keywords in self._pipes:
            if suggested is None:
                suggested = [self.kwds[k] for k in keywords]
            self._pipes[keywords].send((suggested, obj))
        else:
            warnings.warn(f'No feedback pipe for {keywords}', RuntimeWarning,
                          2)

    def feed(self, obj, **options):
        for tracker in self._trackers:
            tracker.feed(self, obj, **options)

    def store(self, obj, **options):
        self.feed(obj, store=True, **options)

    def __getstate__(self):
        state = self.__dict__.copy()
        del state['_pipes']
        del state['_trackers']
        return state

    def __setstate__(self, state):
        self.__dict__ = state
        self._pipes = {}
        self._trackers = []


@dataclass
class StepStatus(FeedbackProxy):
    iteration: int = 0
    pos: tuple = ()
    index: tuple = ()
    kwds: dict = field(default_factory=dict)
    vars: list[str] = field(default=list)
    unchanged: int = 0

    _pipes: dict = field(default_factory=dict, repr=False)
    _trackers: list = field(default_factory=list, repr=False)


@dataclass
class Begin(FeedbackProxy):
    level: int = 0
    iteration: int = 0
    pos: tuple = ()
    index: tuple = ()
    kwds: dict = field(default_factory=dict)
    vars: list[str] = field(default=list)

    _pipes: dict = field(default_factory=dict, repr=False)
    _trackers: list = field(default_factory=list, repr=False)

    def __repr__(self):
        return f'Begin(level={self.level}, kwds={self.kwds}, vars={self.vars})'


@dataclass
class End(FeedbackProxy):
    level: int = 0
    iteration: int = 0
    pos: tuple = ()
    index: tuple = ()
    kwds: dict = field(default_factory=dict)
    vars: list[str] = field(default=list)

    _pipes: dict = field(default_factory=dict, repr=False)
    _trackers: list = field(default_factory=list, repr=False)

    def __repr__(self):
        return f'End(level={self.level}, kwds={self.kwds}, vars={self.vars})'


class Tracker():

    def init(self, loops: dict, functions: dict, constants: dict, graph: dict,
             order: list):
        pass

    def update(self, kwds: dict):
        return kwds

    def feed(self, step: StepStatus, obj: Any, **options):
        pass


def _call_func_with_kwds(func, args, kwds):
    funcname = getattr(func, '__name__', repr(func))
    sig = inspect.signature(func)
    for p in sig.parameters.values():
        if p.kind == p.VAR_KEYWORD:
            return func(*args, **kwds)
    kw = {
        k: v
        for k, v in kwds.items()
        if k in list(sig.parameters.keys())[len(args):]
    }
    try:
        args = [
            arg.result() if isinstance(arg, Future) else arg for arg in args
        ]
        kw = {
            k: v.result() if isinstance(v, Future) else v
            for k, v in kw.items()
        }
        return func(*args, **kw)
    except:
        log.exception(f'Call {funcname} with {args} and {kw}')
        raise
    finally:
        log.debug(f'Call {funcname} with {args} and {kw}')


def _try_to_call(x, args, kwds):
    if callable(x):
        return _call_func_with_kwds(x, args, kwds)
    return x


def _get_current_iters(loops, level, kwds, pipes):
    keys, current = loops[level]
    limit = -1

    if isinstance(keys, str):
        keys = (keys, )
        current = (current, )
    elif isinstance(keys, tuple) and isinstance(
            current, tuple) and len(keys) == len(current):
        keys = tuple(k if isinstance(k, tuple) else (k, ) for k in keys)
    elif isinstance(keys, tuple) and not isinstance(current, tuple):
        current = (current, )
        if isinstance(keys[0], str):
            keys = (keys, )
    else:
        log.error(f'Illegal keys {keys} on level {level}.')
        raise TypeError(f'Illegal keys {keys} on level {level}.')

    if not isinstance(keys, tuple):
        keys = (keys, )
    if not isinstance(current, tuple):
        current = (current, )

    iters = []
    for k, it in zip(keys, current):
        pipe = FeedbackPipe(k)
        if isinstance(it, OptimizerConfig):
            if limit < 0 or limit > it.max_iters:
                limit = it.max_iters
            it = it.cls(it.dimensions, *it.args, **it.kwds)
        else:
            it = iter(_try_to_call(it, (), kwds))

        iters.append((it, pipe))
        pipes[k] = pipe

    return keys, iters, pipes, limit


def _generate_kwds(keys, iters, kwds, iteration, limit):
    ret = {}
    for ks, it in zip(keys, iters):
        if isinstance(ks, str):
            ks = (ks, )
        if hasattr(it[0], 'ask') and hasattr(it[0], 'tell') and hasattr(
                it[0], 'get_result'):
            if limit > 0 and iteration >= limit - 1:
                value = _call_func_with_kwds(it[0].get_result, (), kwds).x
            else:
                value = _call_func_with_kwds(it[0].ask, (), kwds)
        else:
            value = next(it[0])
            if len(ks) == 1:
                value = (value, )
        ret.update(zip(ks, value))
    return ret


def _send_feedback(generator, feedback):
    if hasattr(generator, 'ask') and hasattr(generator, 'tell') and hasattr(
            generator, 'get_result'):
        generator.tell(
            *[x.result() if isinstance(x, Future) else x for x in feedback])


def _feedback(iters):
    for generator, pipe in iters:
        for feedback in pipe():
            _send_feedback(generator, feedback)


def _call_functions(functions, kwds, order, pool: Executor | None = None):
    vars = []
    for i, ready in enumerate(order):
        rest = []
        for k in ready:
            if k in kwds:
                continue
            elif k in functions:
                if pool is None:
                    kwds[k] = _try_to_call(functions[k], (), kwds)
                else:
                    kwds[k] = pool.submit(_try_to_call, functions[k], (), kwds)
                vars.append(k)
            else:
                rest.append(k)
        if rest:
            break
    else:
        return [], vars
    if rest:
        return [rest] + order[i:], vars
    else:
        return order[i:], vars


def _args_generator(loops: list,
                    kwds: dict[str, Any],
                    level: int,
                    pos: tuple[int, ...],
                    vars: list[tuple[str]],
                    filter: Callable[..., bool] | None,
                    functions: dict[str, Callable],
                    trackers: list[Tracker],
                    pipes: dict[str | tuple[str, ...], FeedbackPipe],
                    order: list[str],
                    pool: Executor | None = None):
    order, local_vars = _call_functions(functions, kwds, order, pool)
    if len(loops) == level and level > 0:
        if order:
            log.error(f'Unresolved functions: {order}')
            raise TypeError(f'Unresolved functions: {order}')
        for tracker in trackers:
            kwds = tracker.update(kwds)
        if filter is None or _call_func_with_kwds(filter, (), kwds):
            yield StepStatus(
                pos=pos,
                kwds=kwds,
                vars=[*vars[:-1], tuple([*vars[-1], *local_vars])],
                _pipes=pipes,
                _trackers=trackers)
        return

    keys, current_iters, pipes, limit = _get_current_iters(
        loops, level, kwds, pipes)

    for i in count():
        if limit > 0 and i >= limit:
            break
        try:
            kw = _generate_kwds(keys, current_iters, kwds, i, limit)
        except StopIteration:
            break
        yield Begin(level=level,
                    pos=pos + (i, ),
                    kwds=kwds | kw,
                    vars=[*vars, tuple([*local_vars, *kw.keys()])],
                    _pipes=pipes,
                    _trackers=trackers)
        yield from _args_generator(
            loops, kwds | kw, level + 1, pos + (i, ),
            [*vars, tuple([*local_vars, *kw.keys()])], filter, functions,
            trackers, pipes, order)
        yield End(level=level,
                  pos=pos + (i, ),
                  kwds=kwds | kw,
                  vars=[*vars, tuple([*local_vars, *kw.keys()])],
                  _pipes=pipes,
                  _trackers=trackers)
        _feedback(current_iters)


def _find_common_prefix(a: tuple, b: tuple):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return i


def _add_dependence(graph, keys, function, loop_names, var_names):
    if isinstance(keys, str):
        keys = (keys, )
    for key in keys:
        graph.setdefault(key, set())
        for k, p in inspect.signature(function).parameters.items():
            if p.kind in [
                    p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY
            ] and k in var_names:
                graph[key].add(k)
            if p.kind == p.VAR_KEYWORD and key not in loop_names:
                graph[key].update(loop_names)


def _build_dependence(loops, functions, constants, loop_deps=True):
    graph = {}
    loop_names = set()
    var_names = set()
    for keys, iters in loops.items():
        level_vars = set()
        if isinstance(keys, str):
            keys = (keys, )
        if callable(iters):
            iters = tuple([iters for _ in keys])
        for ks, iter_vars in zip(keys, iters):
            if isinstance(ks, str):
                ks = (ks, )
            if callable(iters):
                iter_vars = tuple([iter_vars for _ in ks])
            level_vars.update(ks)
            for i, k in enumerate(ks):
                d = graph.setdefault(k, set())
                if loop_deps:
                    d.update(loop_names)
                else:
                    if isinstance(iter_vars, tuple):
                        iter_var = iter_vars[i]
                    else:
                        iter_var = iter_vars
                    if callable(iter_var):
                        d.update(
                            set(
                                inspect.signature(iter_vars).parameters.keys())
                            & loop_names)

        loop_names.update(level_vars)
        var_names.update(level_vars)
    var_names.update(functions.keys())
    var_names.update(constants.keys())

    for keys, values in chain(loops.items(), functions.items()):
        if callable(values):
            _add_dependence(graph, keys, values, loop_names, var_names)
        elif isinstance(values, tuple):
            for ks, v in zip(keys, values):
                if callable(v):
                    _add_dependence(graph, ks, v, loop_names, var_names)

    return graph


def _get_all_dependence(key, graph):
    ret = set()
    if key not in graph:
        return ret
    for k in graph[key]:
        ret.add(k)
        ret.update(_get_all_dependence(k, graph))
    return ret


def scan_iters(loops: dict[str | tuple[str, ...],
                           Iterable | Callable | OptimizerConfig
                           | tuple[Iterable | Callable | OptimizerConfig,
                                   ...]] = {},
               filter: Callable[..., bool] | None = None,
               functions: dict[str, Callable] = {},
               constants: dict[str, Any] = {},
               trackers: list[Tracker] = [],
               level_marker: bool = False,
               pool: Executor | None = None,
               **kwds) -> Iterable[StepStatus]:
    """
    Scan the given iterable of iterables.

    Parameters
    ----------
    loops : dict
        A map of iterables that are scanned.
    filter : Callable[..., bool]
        A filter function that is called for each step.
        If it returns False, the step is skipped.
    functions : dict
        A map of functions that are called for each step.
    constants : dict
        Additional keyword arguments that are passed to the iterables.

    Returns
    -------
    Iterable[StepStatus]
        An iterable of StepStatus objects.

    Examples
    --------
    >>> iters = {
    ...     'a': range(2),
    ...     'b': range(3),
    ... }
    >>> list(scan_iters(iters))
    [StepStatus(iteration=0, pos=(0, 0), index=(0, 0), kwds={'a': 0, 'b': 0}),
     StepStatus(iteration=1, pos=(0, 1), index=(0, 1), kwds={'a': 0, 'b': 1}),
     StepStatus(iteration=2, pos=(0, 2), index=(0, 2), kwds={'a': 0, 'b': 2}),
     StepStatus(iteration=3, pos=(1, 0), index=(1, 0), kwds={'a': 1, 'b': 0}),
     StepStatus(iteration=4, pos=(1, 1), index=(1, 1), kwds={'a': 1, 'b': 1}),
     StepStatus(iteration=5, pos=(1, 2), index=(1, 2), kwds={'a': 1, 'b': 2})]

    >>> iters = {
    ...     'a': range(2),
    ...     'b': range(3),
    ... }
    ... list(scan_iters(iters, lambda a, b: a < b))
    [StepStatus(iteration=0, pos=(0, 1), index=(0, 0), kwds={'a': 0, 'b': 1}),
     StepStatus(iteration=1, pos=(0, 2), index=(0, 1), kwds={'a': 0, 'b': 2}),
     StepStatus(iteration=2, pos=(1, 2), index=(1, 0), kwds={'a': 1, 'b': 2})]
    """

    # TODO: loops 里的 callable 值如果有 VAR_KEYWORD 参数，并且在运行时实际依
    #       赖于 functions 里的某些值，则会导致依赖关系错误
    # TODO: functions 里的 callable 值如果有 VAR_KEYWORD 参数，则对这些参数
    #       的依赖会被认为是对全体循环参数的依赖，并且这些函数本身不存在相互依赖

    if 'additional_kwds' in kwds:
        functions = functions | kwds['additional_kwds']
        warnings.warn(
            "The argument 'additional_kwds' is deprecated, "
            "use 'functions' instead.", DeprecationWarning)
    if 'iters' in kwds:
        loops = loops | kwds['iters']
        warnings.warn(
            "The argument 'iters' is deprecated, "
            "use 'loops' instead.", DeprecationWarning)

    if len(loops) == 0:
        return

    graph = _build_dependence(loops, functions, constants)
    ts = TopologicalSorter(graph)
    order = []
    ts.prepare()
    while ts.is_active():
        ready = ts.get_ready()
        for k in ready:
            ts.done(k)
        order.append(ready)
    graph = _build_dependence(loops, functions, constants, False)

    for tracker in trackers:
        tracker.init(loops, functions, constants, graph, order)

    last_step = None
    index = ()
    iteration = count()

    for step in _args_generator(list(loops.items()),
                                kwds=constants,
                                level=0,
                                pos=(),
                                vars=[],
                                filter=filter,
                                functions=functions,
                                trackers=trackers,
                                pipes={},
                                order=order,
                                pool=pool):
        if isinstance(step, (Begin, End)):
            if level_marker:
                if last_step is not None:
                    step.iteration = last_step.iteration
                yield step
            continue

        if last_step is None:
            i = 0
            index = (0, ) * len(step.pos)
        else:
            i = _find_common_prefix(last_step.pos, step.pos)
            index = tuple((j <= i) * n + (j == i) for j, n in enumerate(index))
        step.iteration = next(iteration)
        step.index = index
        step.unchanged = i
        yield step
        last_step = step

