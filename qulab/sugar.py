import asyncio
from urllib.parse import urlparse

from qulab._config import config, config_dir
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


def getBootstrapNodes():
    kad = config_dir() / 'kad.dat'
    if kad.exists():
        with kad.open() as f:
            bootstrap_nodes = f.readlines()
    else:
        bootstrap_nodes = []
    bootstrap_nodes.extend(DHT_config.get('bootstrap_nodes', []))

    def parse(s):
        x = urlparse(s)
        return x.hostname, x.port

    bootstrap_nodes = set(map(parse, bootstrap_nodes))
    return list(bootstrap_nodes)


def saveDHTNodes():
    if __dht is None:
        return
    if not config_dir().exists():
        config_dir().mkdir(parents=True)
    kad = config_dir() / 'kad.dat'
    nodes = __dht.bootstrappable_neighbors()
    nodes.append((getHostIP(), __dht.port))
    kad.write_text('\n'.join(
        ["%s:%d" % (node[0], node[1]) for node in set(nodes)]))
    loop = asyncio.get_event_loop()
    loop.call_later(600, saveDHTNodes)


async def getDHT():
    global __dht
    if __dht is None:
        __dht = DHT()
        await __dht.start(getBootstrapNodes())
        saveDHTNodes()
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
