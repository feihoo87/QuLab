import inspect

import ipywidgets as widgets
import numpy as np
from IPython.display import display

from qulab.bootstrap import (get_current_notebook, get_inputCells,
                             save_inputCells)
from qulab.storage.connect import require_db
from qulab.storage.schema import Record
from qulab.ui.progressbar import ProgressBar


class DataCollector:
    '''
    Collect data and form a record.
    '''

    def __init__(self, title, tags=None, comment='', job=None):
        self.title = title
        self.tags = [] if tags is None else tags
        self.comment = comment
        self.job = job
        self.clear()

    def clear(self):
        self.__data = None
        self.__rows = 0
        self.__cols = 0
        self.__record = None

    @property
    def cols(self):
        return self.__cols

    @property
    def rows(self):
        return self.__rows

    def collect(self, data):
        '''对于存在循环的实验，将每一轮生成的数据收集起来'''
        if not isinstance(data, tuple):
            data = (data, )
        if self.__data is None:
            self.__data = [[v] for v in data]
            self.__cols = len(data)
            self.__rows = 1
        else:
            for i, v in enumerate(data):
                self.__data[i].append(v)
            self.__rows += 1

    def result(self):
        '''将收集到的数据按 work 生成时的顺序返回'''
        if self.__rows == 0:
            return None
        if self.__rows == 1:
            data = tuple([v[0] for v in self.__data])
        else:
            data = tuple([np.array(v) for v in self.__data])
        if self.__cols == 1:
            return self.pre_save(data[0])
        else:
            return self.pre_save(*data)

    @require_db
    def save(self):
        if self.__record is None:
            self.__record = self.newRecord()
        self.__record.set_data(self.result())
        self.__record.save(signal_kwargs=dict(finished=True))

    @require_db
    def newRecord(self):
        save_inputCells()
        record = Record(title=self.title,
                        tags=self.tags,
                        comment=self.comment,
                        hidden=False if self.job.parent is None else True,
                        notebook=get_current_notebook(),
                        notebook_index=len(get_inputCells()) - 1)
        if self.job.parent is not None:
            self.job.parent.data.addSubRecord(record)
        return record

    @require_db
    def addSubRecord(self, record):
        if self.__record is None:
            self.__record = self.newRecord()
        if record.id is None:
            record.save(signal_kwargs=dict(finished=True))
        self.__record.children.append(record)
        self.__record.save(signal_kwargs=dict(finished=True))

    def pre_save(self, *data):
        return data


class Job:
    _running_jobs = []

    def __init__(self,
                 work,
                 args=(),
                 kw={},
                 max=100,
                 title=None,
                 tags=None,
                 comment='',
                 auto_save=None,
                 no_bar=False):
        title = work.__name__ if title is None else title
        self.parent = Job.current_job()
        if auto_save is None:
            self.auto_save = True if self.parent is None else False
        else:
            self.auto_save = auto_save
        self.data = DataCollector(title, tags=tags, comment=comment, job=self)
        self.bar = ProgressBar(max=max, description=title, hiden=no_bar)
        self.out = widgets.Output()
        display(self.out)
        self.work_code = None
        code = compile(inspect.getsource(work),
                       f'defintion of {work.__name__}', 'single')
        for c in code.co_consts:
            if isinstance(c, type(code)) and c.co_name == work.__name__:
                self.work_code = c
                break
        self.work = work
        self.args = args
        self.kw = kw

    def _setUp(self):
        pass

    def _tearDown(self):
        pass

    async def done(self):
        Job._running_jobs.append(self)
        with self.out, self.bar:
            self.data.clear()
            self._setUp()
            async for data in self.work(*self.args, **self.kw):
                self.data.collect(data)
                if self.auto_save:
                    self.data.save()
                self.bar.next()
            self._tearDown()
        Job._running_jobs.remove(self)
        if self.parent is not None:
            self.out.close()
        return self.data.result()

    def __del__(self):
        try:
            self.out.close()
        except:
            pass

    @classmethod
    def current_job(cls):
        if len(cls._running_jobs) > 0:
            return cls._running_jobs[-1]
        else:
            return None
