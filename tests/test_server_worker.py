import asyncio

import pytest

from qulab.server.worker import *

class DemoWorker(QSWorker):
    def do(self, task):
        if task.kw.get('except_test', False):
            raise Exception('test')
        for i in range(5):
            yield task.kw['a'] * task.kw['b']

@pytest.fixture
def worker():
    worker = DemoWorker()
    yield worker
    worker.terminate()

@pytest.fixture
def service():
    service = QulabService()
    yield service
    service.terminate()

async def test_worker(loop, worker):
    assert not worker.is_running()
    worker.start()
    assert worker.procces.is_alive()
    assert worker.is_running()
    result = worker.apply(QSTask(a=1,b=2))
    result2= worker.apply(QSTask(a=5,b=6))
    async for v in result2:
        assert v == 5*6
    async for v in result:
        assert v == 1*2
    worker.stop()
    worker.join()
    assert not worker.procces.is_alive()
    assert not worker.is_running()
    worker.start()
    assert worker.procces.is_alive()
    worker.terminate()
    await asyncio.sleep(0.5)
    print(worker.procces)
    assert not worker.procces.is_alive()
    worker.start()
    assert worker.procces.is_alive()
    worker.terminate()
    await asyncio.sleep(0.5)
    assert not worker.procces.is_alive()
    worker.start()
    assert worker.procces.is_alive()
    result = worker.apply(QSTask(a=1,b=2))
    result2= worker.apply(QSTask(a=5,b=6))
    async for v in result:
        assert v == 1*2
    async for v in result2:
        assert v == 5*6
    result = worker.apply(QSTask(except_test=True))
    with pytest.raises(Exception):
        await result.result()
    worker.stop()
    worker.join()
    assert not worker.procces.is_alive()


async def test_qulabservice(loop, service):
    service.register('test', DemoWorker, {})
    fut1 = service.apply('test', QSTask(a=1,b=2))
    fut2= service.apply('test', QSTask(a=5,b=6))
    async for v in fut2:
        assert v == 5*6
    async for v in fut1:
        assert v == 1*2
    await asyncio.sleep(0.1, loop=loop)


async def test_instrumentworker(loop, service):
    try:
        from instruments import cfg, info
    except:
        pytest.skip("requires instruments")
    for name, address, driver, backends in cfg:
        service.register(name, QSInstrumentWorker, {
            'address': address,
            'driver': driver,
            'backends': backends
        })
    for name in info:
        fut = service.apply(name, QSTask(method='query', args=('*IDN?',), kw={}))
        async for msg in fut:
            assert msg.strip('" \n\'') == info[name]
    service.apply('MW2', QSTask(method='setValue', args=('Frequency', 6e9), kw={}))
    fut = service.apply('MW2', QSTask(method='getValue', args=('Frequency',), kw={}))
    async for f in fut:
        assert f == 6e9
