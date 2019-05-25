#from qulab.sugar import connect, create_server
import numpy as np
import pytest
from qulab.sugar import *


class Channel:
    wav = None

    def set_wav(self, data):
        self.wav = data

    def get_wav(self):
        return self.wav


class Qubit:
    tlist = None
    x_channel = None

    def set_tlist(self, tlist):
        self.tlist = tlist

    async def set_x_channel(self, name):
        self.x_channel = await connect(name)

    async def set_t(self, t):
        x = np.linspace(-5000, 5000, 10001)

        def f(x, sigma):
            return np.exp(-(x / sigma)**2)

        y = f(x - t, sigma=20)
        await self.x_channel.set_wav(y)

    async def getT1(self):
        x, y = [], []
        for t in self.tlist:
            await self.set_t(t)
            p1 = await self.getP1()
            x.append(t)
            y.append(p1)
        return x, y

    async def getP1(self):
        return np.random.randn()


@pytest.fixture
async def server(event_loop):
    s1 = await mount(Qubit(), 'qubit', loop=event_loop)
    s2 = await mount(Channel(), 'ch1', loop=event_loop)
    await asyncio.sleep(0.1)
    yield s1, s2
    s1.close()
    s2.close()


@pytest.mark.asyncio
async def test_mount(server, event_loop):
    s1, s2 = server
    dht = await getDHT()
    addr = await dht.get('qubit')
    assert addr == ('tcp://%s:%d' % (getHostIP(), s1.port))


@pytest.mark.asyncio
async def test_node(server, event_loop):
    dht = await getDHT()
    c = await connect('qubit', loop=event_loop)
    await c.connect()
    assert c.zmq_client.addr == await dht.get('qubit')
    assert await c.zmq_client.ping()
    await c.set_tlist(np.linspace(0, 100, 11))
    await c.set_x_channel('ch1')
    x, y = await c.getT1()
    assert len(x) == 11
    wav = await c.x_channel.get_wav()
    x = np.linspace(-5000, 5000, 10001)

    def f(x, sigma):
        return np.exp(-(x / sigma)**2)

    y = f(x - 100, sigma=20)
    assert len(wav) == 10001
    assert np.all(y == wav)
    c.close_all()


@pytest.mark.asyncio
async def test_reconnect(server, event_loop):
    s1, s2 = server

    await asyncio.sleep(0.1)

    c = await connect('qubit', loop=event_loop)
    await c.set_x_channel('ch1')

    await c.set_tlist(np.linspace(0, 100, 11))
    await c.set_x_channel('ch1')
    x, y = await c.getT1()
    assert len(x) == 11
    wav = await c.x_channel.get_wav()
    x = np.linspace(-5000, 5000, 10001)

    def f(x, sigma):
        return np.exp(-(x / sigma)**2)

    y = f(x - 100, sigma=20)
    assert len(wav) == 10001
    assert np.all(y == wav)

    s1.close()

    with pytest.raises(QuLabRPCError):
        await c.set_x_channel('ch1')

    s1 = await mount(Qubit(), 'qubit', loop=event_loop)
    await asyncio.sleep(0.1)
    await c.set_x_channel('ch1')
    wav = await c.x_channel.get_wav()
    assert np.all(y == wav)

    c.close_all()
