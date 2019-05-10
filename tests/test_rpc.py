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

    async def timeout(self):
        await asyncio.sleep(1)

    def error(self):
        raise Error('error')

    def serverError(self):
        return 1 / 0


@pytest.fixture()
def server(event_loop):
    s = Server(MySrv, loop=event_loop)
    s.start()
    yield s
    s.stop()
    s.close()


@pytest.fixture()
def server(event_loop):
    s = ZMQServer(loop=event_loop)
    s.set_module(MySrv())
    s.start()
    yield s
    s.stop()


@pytest.mark.asyncio
async def test_zmqserver(server, event_loop):
    assert server.port != 0


@pytest.mark.asyncio
async def test_zmqclient(server, event_loop):
    c = ZMQClient('tcp://127.0.0.1:%d' % server.port,
                  timeout=0.7,
                  loop=event_loop)
    assert server.port != 0
    assert await c.ping()
    assert 8 == await c.add(3, 5)
    assert 9 == await c.add_async(4, 5)
    assert "hello, world" == await c.sub.hello()
    with pytest.raises(QuLabRPCTimeout):
        await c.timeout()
    ret = await c.timeout(timeout=2)
    assert ret is None
    with pytest.raises(Error):
        await c.error()
    with pytest.raises(QuLabRPCServerError):
        await c.serverError()
    del c
