import asyncio
import inspect

import numpy as np
import pytest

from qulab import config
from qulab.job import Job
from qulab.storage.schema import Record


@pytest.fixture
def mongo_db():
    config['db']['mongodb'] = 'mongodb://localhost:27017/qulabtestdb'
    from qulab.storage.connect import get_connection
    conn = get_connection()
    conn.drop_database('qulabtestdb')
    yield
    conn.drop_database('qulabtestdb')


async def mw(flist):
    for i in flist:
        await asyncio.sleep(0)
        yield i, 0


async def spec(y=0):
    for i in range(10):
        args = (np.linspace(0, 1, 11), )
        a = Job(mw, args, max=11)
        x, y = await a.done()
        yield i, x, y


@pytest.mark.asyncio
async def test_job(mongo_db):
    job = Job(spec, max=10, tags=['x', 'y'], comment='hello, world')
    await job.done()
    record = Record.objects()[0]
    assert record.title == 'spec'
    assert record.work.text == inspect.getsource(spec)
    i, x, y = record.data
    assert np.all(i == np.arange(10))
    assert np.all(x[0] == np.linspace(0, 1, 11))
    assert np.all(y == 0)
