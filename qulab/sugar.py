import asyncio

from qulab._config import config
from qulab.dht.network import Server as DHT
from qulab.dht.network import cfg as DHT_config
from qulab.dht.utils import digest
from qulab.rpc import ZMQClient, ZMQServer
from qulab.utils import getHostIP, getHostIPv6


class Node:
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self.children = []
        self.module = None
        self.fullpath = name if parent is None else self.parent.fullpath + '.' + self.name

    def mount(self):
        pass

    def unmout(self):
        pass


root = Node('')

__dht = None


async def getDHT():
    global __dht
    if __dht is None:
        __dht = DHT()
        await __dht.start()
    return __dht


async def mount(module, path, *, loop=None):
    s = ZMQServer(loop=loop)
    s.set_module(module)
    s.start()
    dht = await getDHT()
    await asyncio.sleep(0.1)
    addr = 'tcp://%s:%d' % (getHostIP(), s.port)
    await dht.set(path, addr)
    return s


def unmount(path):
    pass


async def connect(path, *, loop=None):
    dht = await getDHT()
    addr = await dht.get(path)
    return ZMQClient(addr, loop=loop)
