import asyncio
import functools
import pickle
from collections.abc import Awaitable

import zmq
import zmq.asyncio


class Server:
    def __init__(self, main_class, *args, loop=None, **kw):
        self._ctx = zmq.asyncio.Context.instance()
        self._main_class = main_class
        self._args = args
        self._kw = kw
        self.__port = 0
        self.loop = asyncio.get_event_loop() if loop is None else loop
        self._main_task = None

    def create_main(self):
        return self._main_class(*self._args, **self._kw)

    @property
    def port(self):
        return self.__port

    def start(self):
        self._main_task = asyncio.ensure_future(self.run(), loop=self.loop)

    def stop(self):
        if self._main_task is not None and not self._main_task.done():
            self._main_task.cancel()

    def close(self):
        pass

    async def run(self):
        obj = self.create_main()
        with self._ctx.socket(zmq.ROUTER) as sock:
            self.__port = sock.bind_to_random_port('tcp://*')
            while True:
                addr, msg = await sock.recv_multipart()
                asyncio.ensure_future(self.handle(sock, obj, addr, msg), loop=self.loop)

    async def handle(self, sock, obj, addr, msg):
        method, args, kw = pickle.loads(msg)
        result = getattr(obj, method)(*args, **kw)
        if isinstance(result, Awaitable):
            result = await result
        result = pickle.dumps(result)
        await sock.send_multipart([addr, result])


class RPCCallable:
    def __init__(self, name, owner):
        self.name = name
        self.owner = owner

    def __call__(self, *args, **kw):
        return self.owner.performMethod(self.name, *args, **kw)


class Client:
    def __init__(self, address):
        self._ctx = zmq.asyncio.Context.instance()
        self.sock = self._ctx.socket(zmq.DEALER)
        self.sock.connect(address)

    def __del__(self):
        self.sock.close()

    def __getattr__(self, name):
        return RPCCallable(name, self)

    async def performMethod(self, name, *args, **kw):
        msg = pickle.dumps((name, args, kw))
        await self.sock.send_multipart([msg])
        result, = await self.sock.recv_multipart()
        return pickle.loads(result)
