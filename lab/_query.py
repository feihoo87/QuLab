import functools

from . import db
from .ui import QuerySetUI


class QuerySet():
    def __init__(self, query_set):
        self.query_set = query_set
        self.ui = QuerySetUI(self)
        self.__count = self.count()
        self.__index = 0

    @functools.lru_cache(maxsize=32)
    def __getitem__(self, i):
        i = i % self.count()
        return self.query_set[i]

    def __iter__(self):
        return self

    def __next__(self):
        if self.__index < self.__count:
            item = self.__getitem__(self.__index)
            self.__index += 1
            return item
        else:
            self.__index = 0
            raise StopIteration

    @functools.lru_cache(maxsize=1)
    def count(self):
        return self.query_set.count()

    def display(self, start=None, stop=None,
        cols=['Index', 'Time', 'Title', 'User', 'Tags', 'Parameters', 'Image'], figsize=None):
        if start is None and stop is None:
            stop=self.count()
            start=stop-10
            if start < 0:
                start=0
        self.ui.display(start, stop, cols, figsize)

def query(app=None, show_hidden=False, q=None, **kwds):
    return QuerySet(db.query.query_records(q=q, app=app, show_hidden=show_hidden, **kwds))
