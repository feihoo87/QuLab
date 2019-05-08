import asyncio
import functools
from collections.abc import Awaitable

import zmq
import zmq.asyncio
from qulab.serialize import pack, unpack
from qulab.utils import randomID


class RPCException(Exception):
    """
    Base exception.
    """


class RPCServerError(RPCException):
    """
    Server side error.
    """


class RPCTimeout(RPCException):
    """
    Timeout.
    """


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
                addr, msgID, msg = await sock.recv_multipart()
                asyncio.ensure_future(self.handle(sock, obj, addr, msgID, msg),
                                      loop=self.loop)

    async def handle(self, sock, obj, addr, msgID, msg):
        method, args, kw = unpack(msg)
        if method == 'rpc_is_alive':
            result = True
        else:
            try:
                result = getattr(obj, method)(*args, **kw)
                if isinstance(result, Awaitable):
                    result = await result
            except RPCException as e:
                result = e
            except Exception as e:
                result = RPCServerError(*e.args)
        result = pack(result)
        await sock.send_multipart([addr, msgID, result])


class RPCCallable:
    def __init__(self, name, owner):
        self.name = name
        self.owner = owner

    def __call__(self, *args, **kw):
        return self.owner.performMethod(self.name, *args, **kw)


class Client:
    def __init__(self, address, timeout=1, loop=None):
        self._ctx = zmq.asyncio.Context.instance()
        self.sock = self._ctx.socket(zmq.DEALER)
        self.sock.connect(address)
        self._timeout = timeout
        self.loop = asyncio.get_event_loop() if loop is None else loop
        self.pending = {}
        self._main_task = asyncio.ensure_future(self._listen(), loop=self.loop)

    def __del__(self):
        self.sock.close()
        for fut, timeout in self.pending.values():
            timeout.cancel()
            fut.cancel()
        self._main_task.cancel()

    def __getattr__(self, name):
        return RPCCallable(name, self)

    async def _listen(self):
        while True:
            msgID, bmsg = await self.sock.recv_multipart()
            self.on_bmsg(msgID, bmsg)

    def on_bmsg(self, msgID, bmsg):
        if msgID not in self.pending:
            return
        fut, timeout = self.pending[msgID]
        result = unpack(bmsg)
        timeout.cancel()
        if isinstance(result, Exception):
            fut.set_exception(result)
        else:
            fut.set_result(result)
        del self.pending[msgID]

    def _cancel_when_timeout(self, msgID):
        fut, timeout = self.pending[msgID]
        fut.set_exception(RPCTimeout('Time out.'))
        del self.pending[msgID]

    def performMethod(self, name, *args, **kw):
        if 'timeout' in kw:
            delay = kw['timeout']
            del kw['timeout']
        else:
            delay = self._timeout
        msg = pack((name, args, kw))
        msgID = randomID()
        asyncio.ensure_future(self.sock.send_multipart([msgID, msg]),
                              loop=self.loop)
        fut = self.loop.create_future()
        timeout = self.loop.call_later(delay, self._cancel_when_timeout, msgID)
        self.pending[msgID] = (fut, timeout)
        return fut

    def rpc_is_alive(self, **kw):
        return self.performMethod('rpc_is_alive', **kw)
