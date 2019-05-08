import pytest
from qulab.rpc import *


class Error(RPCException):
    pass


@pytest.fixture()
def main_class():
    class MySrv:
        def __init__(self, sid=''):
            self.sid = sid

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
            return 1/0

    yield MySrv


@pytest.fixture()
def server(main_class, event_loop):
    s = Server(main_class, loop=event_loop)
    s.start()
    yield s
    s.stop()
    s.close()


@pytest.mark.asyncio
async def test_Server(server, event_loop):
    obj = server.create_main()
    assert server.port != 0
    assert hasattr(obj, 'add')


@pytest.mark.asyncio
async def test_Client(server, event_loop):
    c = Client('tcp://127.0.0.1:%d' % server.port,
               timeout=0.7,
               loop=event_loop)
    assert server.port != 0
    assert await c.rpc_ping()
    assert 8 == await c.add(3, 5)
    assert 9 == await c.add_async(4, 5)
    with pytest.raises(RPCTimeout):
        await c.timeout()
    ret = await c.timeout(timeout=2)
    assert ret is None
    with pytest.raises(Error):
        await c.error()
    with pytest.raises(RPCServerError):
        await c.serverError()
    del c
