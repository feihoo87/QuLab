import bisect
from concurrent.futures import Future
from datetime import datetime
from itertools import chain
from multiprocessing import Lock
from queue import Queue
from typing import Any, Sequence

from ..scan.base import StepStatus, Tracker, _get_all_dependence

_NODEFAULT = object()


class BaseDataset(Tracker):
    """
    A tracker that stores the results of the steps.

    Parameters
    ----------
    data : dict
        The data of the results.
    shape : tuple
        The shape of the results.
    ctime : datetime.datetime
        The creation time of the tracker.
    mtime : datetime.datetime
        The modification time of the tracker.
    """

    def __init__(
            self,
            data: dict = None,
            shape: tuple = (),
            save_kwds: bool | Sequence[str] = True,
            frozen_keys: tuple = (),
            ignores: tuple = (),
    ):
        self.ctime = datetime.utcnow()
        self.mtime = datetime.utcnow()
        self.data = data if data is not None else {}
        self.cache = {}
        self.pos = {}
        self.timestamps = {}
        self.iteration = {}
        self._init_keys = list(self.data.keys())
        self._frozen_keys = frozen_keys
        self._ignores = ignores
        self._key_levels = ()
        self.depends = {}
        self.dims = {}
        self.vars_dims = {}
        self.shape = shape
        self.count = 0
        self.save_kwds = save_kwds
        self.queue = Queue()
        self._queue_buffer = None
        self._lock = Lock()

    def init(self, loops: dict, functions: dict, constants: dict, graph: dict,
             order: list):
        """
        Initialize the tracker.

        Parameters
        ----------
        loops : dict
            The map of iterables.
        functions : dict
            The map of functions.
        constants : dict
            The map of constants.
        graph : dict
            The dependence graph.
        order : list
            The order of the dependence graph.
        """
        from numpy import ndarray

        self.depends = graph

        for level, (keys, iters) in enumerate(loops.items()):
            self._key_levels = self._key_levels + ((keys, level), )
            if isinstance(keys, str):
                keys = (keys, )
                iters = (iters, )
            if (len(keys) > 1 and len(iters) == 1
                    and isinstance(iters[0], ndarray) and iters[0].ndim == 2
                    and iters[0].shape[1] == len(keys)):
                iters = iters[0]
                for i, key in enumerate(keys):
                    self.data[key] = iters[:, i]
                    self._frozen_keys = self._frozen_keys + (key, )
                    self._init_keys.append(key)
                continue
            if not isinstance(iters, tuple) or len(keys) != len(iters):
                continue
            for key, iter in zip(keys, iters):
                if self.depends.get(key, set()):
                    dims = set()
                    for dep in self.depends[key]:
                        if dep in self.vars_dims:
                            dims.update(set(self.vars_dims[dep]))
                    dims.add(level)
                    self.vars_dims[key] = tuple(sorted(dims))
                else:
                    self.vars_dims[key] = (level, )
                if level not in self.dims:
                    self.dims[level] = ()
                self.dims[level] = self.dims[level] + (key, )
                if key not in self.data and isinstance(iter,
                                                       (list, range, ndarray)):
                    if key.startswith('__'):
                        continue
                    self.data[key] = iter
                    self._frozen_keys = self._frozen_keys + (key, )
                    self._init_keys.append(key)

        for key, value in constants.items():
            if key.startswith('__'):
                continue
            self.data[key] = value
            self._init_keys.append(key)
            self.vars_dims[key] = ()

        for ready in order:
            for key in ready:
                if key in functions:
                    deps = _get_all_dependence(key, graph)
                    dims = set()
                    for k in deps:
                        dims.update(set(self.vars_dims.get(k, ())))
                    self.vars_dims[key] = tuple(sorted(dims))

        for k, v in self.vars_dims.items():
            if len(v) == 1:
                if v[0] in self.dims and k not in self.dims[v[0]]:
                    self.dims[v[0]] = self.dims[v[0]] + (k, )
                elif v[0] not in self.dims:
                    self.dims[v[0]] = (k, )

    def feed(self,
             step: StepStatus,
             dataframe: dict | Future,
             store=False,
             **options):
        """
        Feed the results of the step to the dataset.

        Parameters
        ----------
        step : StepStatus
            The step.
        dataframe : dict
            The results of the step.
        """
        import numpy as np

        if not store:
            return
        self.mtime = datetime.utcnow()
        if not self.shape:
            self.shape = tuple([i + 1 for i in step.pos])
        else:
            self.shape = tuple(
                [max(i + 1, j) for i, j in zip(step.pos, self.shape)])
        if self.save_kwds:
            if isinstance(self.save_kwds, bool):
                kwds = step.kwds
            else:
                kwds = {
                    key: step.kwds.get(key, np.nan)
                    for key in self.save_kwds
                }
        else:
            kwds = {}

        if isinstance(dataframe, dict):
            dataframe = self._prune(dataframe)
        self.queue.put_nowait(
            (step.iteration, step.pos, dataframe, kwds, self.mtime))
        self.flush()

    def _prune(self, dataframe: dict[str, Any]) -> dict[str, Any]:
        return {
            k: v
            for k, v in dataframe.items() if k not in self._ignores
            and k not in self._frozen_keys and not k.startswith('__')
        }

    def _append(self, iteration, pos, dataframe, kwds, now):
        for k, v in chain(kwds.items(), dataframe.items()):
            if k in self._frozen_keys or k in self._ignores:
                continue
            if k.startswith('__'):
                continue
            if self.vars_dims.get(k, ()) == () and k not in dataframe:
                continue
            self.count += 1
            if k not in self.data:
                self.data[k] = [v]
                if k in self.vars_dims:
                    self.pos[k] = tuple([pos[i]] for i in self.vars_dims[k])
                else:
                    self.pos[k] = tuple([i] for i in pos)
                self.timestamps[k] = [now.timestamp()]
                self.iteration[k] = [iteration]
            else:
                if k in self.vars_dims:
                    pos_k = tuple(pos[i] for i in self.vars_dims[k])
                    if k not in dataframe and pos_k in zip(*self.pos[k]):
                        continue
                    for i, l in zip(pos_k, self.pos[k]):
                        l.append(i)
                else:
                    for i, l in zip(pos, self.pos[k]):
                        l.append(i)
                self.timestamps[k].append(now.timestamp())
                self.iteration[k].append(iteration)
                self.data[k].append(v)

    def flush(self, block=False):
        with self._lock:
            self._flush(block=block)

    def _dataframe_done(self, dataframe: Future | dict) -> bool:
        if isinstance(dataframe, Future):
            return dataframe.done()
        else:
            return all(x.done() for x in dataframe.values()
                       if isinstance(x, Future))

    def _dataframe_result(self, dataframe: Future | dict) -> dict:
        if isinstance(dataframe, Future):
            return dataframe.result()
        else:
            return {
                k: v.result() if isinstance(v, Future) else v
                for k, v in dataframe.items()
            }

    def _flush(self, block=False):
        if self._queue_buffer is not None:
            iteration, pos, dataframe, kwds, now = self._queue_buffer
            if self._dataframe_done(dataframe) or block:
                self._append(iteration, pos,
                             self._prune(self._dataframe_result(dataframe)),
                             kwds, now)
                self._queue_buffer = None
            else:
                return
        while not self.queue.empty():
            iteration, pos, dataframe, kwds, now = self.queue.get()
            if not self._dataframe_done(dataframe) and not block:
                self._queue_buffer = (iteration, pos, dataframe, kwds, now)
                return
            else:
                self._append(iteration, pos,
                             self._prune(self._dataframe_result(dataframe)),
                             kwds, now)

    def _get_array(self, key, shape, count):
        import numpy as np

        if key in self.vars_dims:
            shape = tuple([shape[i] for i in self.vars_dims[key]])

        data, data_shape, data_count = self.cache.get(key, (None, (), 0))
        if (data_shape, data_count) == (shape, count):
            return data
        try:
            tmp = np.asarray(self.data[key])
            if data_shape != shape:
                data = np.full(shape + tmp.shape[1:], np.nan, dtype=tmp.dtype)
        except:
            tmp = self.data[key]
            if data_shape != shape:
                data = np.full(shape, np.nan, dtype=object)
        try:
            data[self.pos[key]] = tmp
        except:
            raise
        self.cache[key] = (data, shape, count)
        return data

    def _get_part(self, key, skip):
        i = bisect.bisect_left(self.iteration[key], skip)
        pos = tuple(p[i:] for p in self.pos[key])
        iteration = self.iteration[key][i:]
        data = self.data[key][i:]
        return data, iteration, pos

    def keys(self):
        """
        Get the keys of the dataset.
        """
        self.flush()
        return self.data.keys()

    def values(self):
        """
        Get the values of the dataset.
        """
        self.flush()
        return [self[k] for k in self.data]

    def items(self):
        """
        Get the items of the dataset.
        """
        self.flush()
        return list(zip(self.keys(), self.values()))

    def get(self, key, default=_NODEFAULT, skip=None, block=False):
        """
        Get the value of the dataset.
        """
        self.flush(block)
        if key in self._init_keys:
            return self.data[key]
        elif key in self.data:
            if skip is None:
                return self._get_array(key, self.shape, self.count)
            else:
                return self._get_part(key, skip)
        elif default is _NODEFAULT:
            raise KeyError(key)
        else:
            return default

    def __getitem__(self, key):
        return self.get(key)

    def __getstate__(self):
        self.flush()
        data = dict(self.items())
        return {
            'data': data,
            'pos': self.pos,
            'timestamps': self.timestamps,
            'iteration': self.iteration,
            'depends': self.depends,
            'shape': self.shape,
            'dims': self.dims,
            'vars_dims': self.vars_dims,
            'ctime': self.ctime,
            'mtime': self.mtime,
            '_init_keys': self._init_keys,
            '_frozen_keys': self._frozen_keys,
            '_ignores': self._ignores,
            '_key_levels': self._key_levels,
            'save_kwds': self.save_kwds,
        }
