import asyncio
from urllib.parse import urlparse

import redis

from qulab._config import config, config_dir
from qulab.dht.network import Server as DHT
from qulab.dht.network import cfg as DHT_config
from qulab.dht.utils import digest
from qulab.exceptions import QuLabRPCError, QuLabRPCTimeout
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
__redis = config['db'].get('redis', None)
if __redis is not None:
    __redis = redis.Redis(**__redis)


def _setAddressOnRedis(path, addr):
    __redis.set(f'qulab_route_table_{path}', addr)


def _getAddressOnRedis(path):
    return __redis.get(f'qulab_route_table_{path}').decode()


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
        ["kad://%s:%d" % (node[0], node[1]) for node in set(nodes)]))
    loop = asyncio.get_event_loop()
    loop.call_later(600, saveDHTNodes)


async def getDHT(reboot=False):
    global __dht
    if reboot:
        __dht.stop()
        __dht = None
    if __dht is None:
        __dht = DHT()
        await __dht.start(getBootstrapNodes())
        saveDHTNodes()
    return __dht


async def mount(module, path, *, loop=None):
    s = ZMQServer(loop=loop)
    s.set_module(module)
    s.start()
    await asyncio.sleep(0.1, loop=loop)
    addr = 'tcp://%s:%d' % (getHostIP(), s.port)
    if __redis is not None:
        _setAddressOnRedis(path, addr)
    dht = await getDHT()
    await dht.set(path, addr)
    return s


def unmount(path):
    pass


class RemoteMethod:
    def __init__(self, name, connection):
        self.name = name
        self.connection = connection

    def __call__(self, *args, **kw):
        return self.connection._remoteCall(self.name, args, kw)

    def __getattr__(self, name):
        return RemoteMethod(f"{self.name}.{name}", self.connection)


class Connection:
    _zmq_client_table = {}

    def __init__(self, path, loop):
        self.path = path
        self.loop = loop
        self.zmq_client = None

    def __getattr__(self, name):
        return RemoteMethod(name, self)

    async def _remoteCall(self, method, args, kw):
        if self.zmq_client is None:
            await self.connect()
        try:
            return await self.zmq_client.remoteCall(self.zmq_client.addr,
                                                    method, args, kw)
        except QuLabRPCTimeout:
            self.zmq_client = None
            raise

    async def _connect(self):
        if __redis is not None:
            addr = _getAddressOnRedis(self.path)
        else:
            dht = await getDHT()
            addr = await dht.get(self.path)
        if addr is None:
            raise QuLabRPCError(f"Unknow RPC path {self.path}.")
        return ZMQClient(addr, loop=self.loop)

    async def connect(self):
        if self.path not in Connection._zmq_client_table:
            Connection._zmq_client_table[self.path] = await self._connect()

        retry = 0
        while retry < 3:
            if not await Connection._zmq_client_table[self.path].ping():
                Connection._zmq_client_table[self.path] = await self._connect()
            else:
                break
            retry += 1
        else:
            raise QuLabRPCError(f'Can not connect to {self.path}')

        self.zmq_client = Connection._zmq_client_table[self.path]

    def close(self):
        self.zmq_client.__del__()
        if self.path in Connection._zmq_client_table:
            del Connection._zmq_client_table[self.path]

    @classmethod
    def close_all(cls):
        for c in cls._zmq_client_table.values():
            try:
                c.close()
            except:
                pass
        cls._zmq_client_table = {}


async def connect(path, *, loop=None):
    dht = await getDHT()
    if isinstance(path, Connection):
        path = path.path
    if __redis is not None:
        addr = _getAddressOnRedis(self.path)
    else:
        addr = await dht.get(path)
    if addr is None:
        raise QuLabRPCError(f'Unknow RPC path {path}.')
    return Connection(path, loop=loop)
