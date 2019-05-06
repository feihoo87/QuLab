import pytest
from qulab.rpc import *

class Error(Exception):
    pass

@pytest.fixture()
def main_class():
    class MySrv:
        def __init__(self, sid=''):
            self.sid = sid

        def add(self, a, b):
            return a + b

        async def add_async(self, a, b):
            await asyncio.sleep(1)
            return a + b

        def error(self):
            raise Error('error')

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
    c = Client('tcp://127.0.0.1:%d' % server.port)
    assert server.port != 0
    assert 8 == await c.add(3, 5)
    assert 9 == await c.add_async(4, 5)
    with pytest.raises(Error):
        await c.error()
