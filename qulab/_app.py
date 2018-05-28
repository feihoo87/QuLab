import abc
import asyncio
import datetime
import functools
import importlib
import os
import sys
import time
import tokenize
from collections import Awaitable, Iterable, OrderedDict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from threading import Thread

import numpy as np


# yapf: disable
class QuLabError(Exception): pass
class QuLabTypeError(QuLabError): pass
class QuLabRuntimeError(QuLabError): pass
# yapf: enable


class MetaHasSource(type):
    '''Metaclass for all types that have attribute `__source__` and `__DBDocument__`
    '''

    def __new__(cls, name, bases, nmspc):
        return super(MetaHasSource, cls).__new__(cls, name, bases, nmspc)

    def __init__(cls, name, bases, nmspc):
        super(MetaHasSource, cls).__init__(name, bases, nmspc)
        if cls.__module__ != 'builtins':
            try:
                cls.__source__ = cls._getSourceCode()
            except:
                cls.__source__ = ''

    def _getSourceCode(cls):
        '''Get the source code of Class so we can record it into database.'''
        module = sys.modules[cls.__module__]
        if module.__name__ == '__main__' and hasattr(module, 'In'):
            code = module.In[-1]
        elif cls.__DBDocument__ is not None:
            try:
                code = cls.__DBDocument__.source
            except:
                raise QuLabTypeError('Document %r has no attribute `source`')
        elif hasattr(module, '__file__'):
            with tokenize.open(module.__file__) as f:
                code = f.read()
        else:
            code = ''
        return code


class HasSource(metaclass=MetaHasSource):
    """Base class that have attribute `__source__` and `__DBDocument__`"""
    @classmethod
    def show(cls):
        """Show source code of class."""
        from .ui import display_source_code
        display_source_code(cls.__source__)


class Application(HasSource):
    """Base class for apps."""

    __source__ = ''
    __DBDocument__ = None

    async def work(self):
        """Overwrite this method to define your work.

        单个返回值不要用 tuple，否则会被解包，下面这些都允许
        yield 0
        yield 0, 1, 2
        yield np.array([1,2,3])
        yield [1,2,3]
        yield 1, (1,2)
        yield 0.5, np.array([1,2,3])
        """

    def pre_save(self, *args):
        return args

    @staticmethod
    def plot(fig, data):
        pass

    @classmethod
    def save(cls, version=None, package=''):
        """Save Application into database."""
        db.update.saveApplication(cls.__name__, cls.__source__,
                                  get_current_user(), package, cls.__doc__,
                                  version)
