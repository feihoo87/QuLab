import pytest
from qulab.rpc import *


class Error(QuLabRPCError):
    pass


class MySrv:
    def __init__(self, sid=''):
        self.sid = sid
        class Test:
            def hello(self):
                return "hello, world"

        self.sub = Test()

    def add(self, a, b):
        return a + b

    async def add_async(self, a, b):
        await asyncio.sleep(0.2)
        return a + b

    def error(self):
        raise Error('error')

    def serverError(self):
        return 1 / 0

    async def sleep(self, t):
        await asyncio.sleep(t)


@pytest.fixture()
def server(event_loop):
    s = ZMQServer(loop=event_loop)
    s.set_module(MySrv())
    s.start()
    yield s
    s.close()


@pytest.mark.asyncio
async def test_zmqserver(server, event_loop):
    assert server.port != 0
    c = ZMQClient('tcp://127.0.0.1:%d' % server.port,
                  timeout=2,
                  loop=event_loop)
    fut = asyncio.ensure_future(c.sleep(100), loop=event_loop)
    await asyncio.sleep(0.1)
    n = len(server.tasks.keys())
    assert n != 0
    try:
        await fut
    except:
        await asyncio.sleep(0.1)
    assert n > len(server.tasks.keys())


@pytest.mark.asyncio
async def test_ping(server, event_loop):
    c = ZMQClient('tcp://127.0.0.1:%d' % server.port,
                  timeout=0.7,
                  loop=event_loop)
    assert await c.ping()
    server.stop()
    assert not await c.ping()
    del c
    c = ZMQClient('tcp://127.0.0.1:%d' % server.port,
                  timeout=0.7,
                  loop=event_loop)
    assert not await c.ping()


@pytest.mark.asyncio
async def test_zmqclient(server, event_loop):
    c = ZMQClient('tcp://127.0.0.1:%d' % server.port,
                  timeout=0.7,
                  loop=event_loop)
    assert 8 == await c.add(3, 5)
    assert 9 == await c.add_async(4, 5)
    assert "hello, world" == await c.sub.hello()
    with pytest.raises(QuLabRPCTimeout):
        await c.sleep(1)
    ret = await c.sleep(1, timeout=2)
    assert ret is None
    with pytest.raises(Error):
        await c.error()
    with pytest.raises(QuLabRPCServerError):
        await c.serverError()
