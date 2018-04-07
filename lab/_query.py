import functools

from . import db
from .ui import QuerySetUI


class QuerySet():
    def __init__(self, query_set):
        self.query_set = query_set
        self.ui = QuerySetUI(self)

    @functools.lru_cache(maxsize=32)
    def __getitem__(self, i):
        return self.query_set[i]

    def __iter__(self):
        self.__count = self.count()
        self.__index = 0
        return self

    def __next__(self):
        if self.__index < self.__count:
            return self.__getitem__(self.__index)
        else:
            raise StopIteration

    def count(self):
        return self.query_set.count()

    def display(self, start=0, stop=10, figsize=None):
        self.ui.display(start, stop, figsize)

def query(app=None, show_hidden=False, q=None, **kwds):
    return QuerySet(db.query.query_records(q=q, app=app, show_hidden=show_hidden, **kwds))
