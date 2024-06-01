from typing import Type

import numpy as np
import skopt
from skopt.space import Categorical, Integer, Real


class Space():

    def __init__(self, function, *args, **kwds):
        self.function = function
        self.args = args
        self.kwds = kwds

    def __repr__(self):
        if self.function == 'asarray':
            return repr(self.args[0])
        args = ', '.join(map(repr, self.args))
        kwds = ', '.join(f'{k}={v!r}' for k, v in self.kwds.items())
        return f"{self.function}({args}, {kwds})"

    def __len__(self):
        return len(self.toarray())

    @classmethod
    def fromarray(cls, array):
        if isinstance(array, Space):
            return array
        if isinstance(array, (list, tuple)):
            array = np.array(array)
        try:
            a = np.linspace(array[0], array[-1], len(array), dtype=array.dtype)
            if np.allclose(a, array):
                return cls('linspace',
                           array[0],
                           array[-1],
                           len(array),
                           dtype=array.dtype)
        except:
            pass
        try:
            a = np.logspace(np.log10(array[0]),
                            np.log10(array[-1]),
                            len(array),
                            base=10,
                            dtype=array.dtype)
            if np.allclose(a, array):
                return cls('logspace',
                           np.log10(array[0]),
                           np.log10(array[-1]),
                           len(array),
                           base=10,
                           dtype=array.dtype)
        except:
            pass
        try:
            a = np.logspace(np.log2(array[0]),
                            np.log2(array[-1]),
                            len(array),
                            base=2,
                            dtype=array.dtype)
            if np.allclose(a, array):
                return cls('logspace',
                           np.log2(array[0]),
                           np.log2(array[-1]),
                           len(array),
                           base=2,
                           dtype=array.dtype)
        except:
            pass
        try:
            a = np.geomspace(array[0],
                             array[-1],
                             len(array),
                             dtype=array.dtype)
            if np.allclose(a, array):
                return cls('geomspace',
                           array[0],
                           array[-1],
                           len(array),
                           dtype=array.dtype)
        except:
            pass
        return array

    def toarray(self):
        return getattr(np, self.function)(*self.args, **self.kwds)


def logspace(start, stop, num=50, endpoint=True, base=10):
    return Space('logspace', start, stop, num, endpoint=endpoint, base=base)


def linspace(start, stop, num=50, endpoint=True):
    return Space('linspace', start, stop, num, endpoint=endpoint)


def geomspace(start, stop, num=50, endpoint=True):
    return Space('geomspace', start, stop, num, endpoint=endpoint)


class OptimizeSpace():

    def __init__(self, optimizer: 'Optimizer', space):
        self.optimizer = optimizer
        self.space = space
        self.name = None

    def __len__(self):
        return self.optimizer.maxiter


class Optimizer():

    def __init__(self,
                 scanner,
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
