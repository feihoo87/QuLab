import asyncio
import functools
from abc import ABC, abstractmethod
from collections.abc import Awaitable

import zmq
import zmq.asyncio
from qulab.exceptions import (QuLabRPCError, QuLabRPCServerError,
                              QuLabRPCTimeout)
from qulab.serialize import pack, unpack
from qulab.utils import acceptArg, randomID

# message type

RPC_REQUEST = b'\x01'
RPC_RESPONSE = b'\x02'
RPC_PING = b'\x03'
PRC_PONG = b'\x04'

class RPCMixin(ABC):
    @property
    @abstractmethod
    def loop(self):
        """
        Event loop.
        """

    @abstractmethod
    async def send_msg(self, address, mtype, msgID, msg):
        """
        Send message to address.
        """

    def unpack(self, msg):
        try:
            method, args, kw = unpack(msg)
        except:
            raise QuLabRPCError("Could not read packet: %r" % msg)
        return method, args, kw


class RPCClientMixin(RPCMixin):
    __pending = None
    _client_defualt_timeout = 1

    def set_timeout(self, timeout=1):
        self._client_timeout = timeout

    @property
    def pending(self):
        if self.__pending is None:
            self.__pending = {}
        return self.__pending

    def close(self):
        for fut in self.pending.values():
            try:
                fut.cancel()
            finally:
                pass

    def cancelWhenTimeout(self, addr, msgID):
        fut, timeout = self.pending[msgID]
        self.cancelRemoteTask(addr, msgID)
        fut.set_exception(QuLabRPCTimeout('Time out.'))
        del self.pending[msgID]

    def cancelRemoteTask(self, addr, msgID):
        msg = pack(('rpc.cancelTask', (msgID, ), {}))
        asyncio.ensure_future(self.send_msg(addr, RPC_REQUEST, msgID, msg), loop=self.loop)

    async def ping(self, addr, timeout=1):
        try:
            await asyncio.wait_for(self.callRemoteMethod(addr, 'rpc.ping'),
                                   timeout,
                                   loop=self.loop)
            return True
        except asyncio.TimeoutError:
            raise QuLabRPCTimeout('Ping %r timeout.' % addr)

    def callRemoteMethod(self, addr, name, *args, **kw):
        if self.loop is None:
            raise QuLabRPCError("Event loop not set.")

        if 'timeout' in kw:
            delay = kw['timeout']
        else:
            delay = self._client_defualt_timeout
        msg = pack((name, args, kw))
        msgID = randomID()
        asyncio.ensure_future(self.send_msg(addr, RPC_REQUEST, msgID, msg), loop=self.loop)
        fut = self.loop.create_future()
        timeout = self.loop.call_later(delay, self.cancelWhenTimeout, addr,
                                       msgID)
        self.pending[msgID] = (fut, timeout)
        return fut

    def on_response(self, msgID, msg):
        """
        Client side.
        """
        if msgID not in self.pending:
            return
        fut, timeout = self.pending[msgID]
        result = unpack(msg)
        timeout.cancel()
        if isinstance(result, Exception):
            fut.set_exception(result)
        else:
            fut.set_result(result)
        del self.pending[msgID]


class RPCServerMixin(RPCMixin):
    __tasks = None

    @property
    def tasks(self):
        if self.__tasks is None:
            self.__tasks = {}
        return self.__tasks

    def close(self):
        for task in self.tasks.values():
            try:
                task.cancel()
            finally:
                pass

    def create_task(self, msgID, coro, timeout=0):
        """
        Create a new task for msgID.
        """
        if timeout > 0:
            coro = asyncio.wait_for(coro, timeout)
        task = asyncio.ensure_future(coro, loop=self.loop)
        self.tasks[msgID] = task

        def clean(fut, msgID=msgID):
            del self.tasks[msgID]

        task.add_done_callback(clean)

    def cancelTask(self, msgID):
        """
        Cancel the task for msgID.
        """
        if msgID in self.tasks:
            self.tasks[msgID].cancel()
            del self.tasks[msgID]

    @abstractmethod
    def getHandler(self, name, source, msgID):
        pass

    def send_result(self, addr, msgID, result):
        """
        Send result to client on addr.
        """
        msg = pack(result)
        return asyncio.ensure_future(self.send_msg(addr, RPC_RESPONSE, msgID, msg),
                                     loop=self.loop)

    def on_request(self, source, msgID, msg):
        """
        Received a request from source.
        """
        try:
            method, args, kw = self.unpack(msg)
            if method == 'rpc.cancelTask':
                self.cancelTask(*args)
            elif method == 'rpc.ping':
                self.send_result(source, msgID, True)
            else:
                self.create_task(msgID,
                                 self.handle(source, msgID, method, *args,
                                             **kw),
                                 timeout=kw.get('timeout', 0))
        except Exception as e:
            self.send_result(source, msgID, QuLabRPCServerError(*e.args))

    async def handle(self, source, msgID, method, *args, **kw):
        """
        Handle a request from source.
        """
        try:
            func = self.getHandler(method, source=source, msgID=msgID)
            if 'timeout' in kw and not acceptArg(func, 'timeout'):
                del kw['timeout']
            result = func(*args, **kw)
            if isinstance(result, Awaitable):
                result = await result
        except QuLabRPCError as e:
            result = e
        except Exception as e:
            result = QuLabRPCServerError(*e.args)
        msg = pack(result)
        await self.send_msg(source, RPC_RESPONSE, msgID, msg)


class ZMQServer(RPCServerMixin):
    def __init__(self, loop=None):
        self.zmq_main_task = None
        self.zmq_ctx = None
        self.zmq_socket = None
        self._port = 0
        self._loop = asyncio.get_event_loop() if loop is None else loop
        self._module = None

    def set_module(self, mod):
        self._module = mod

    async def send_msg(self, address, mtype, msgID, msg):
        self.zmq_socket.send_multipart([address, mtype, msgID, msg])

    def getHandler(self, name, **kw):
        path = name.split('.')
        ret = getattr(self._module, path[0])
        for n in path[1:]:
            ret = getattr(ret, n)
        return ret

    @property
    def loop(self):
        return self._loop

    @property
    def port(self):
        return self._port

    def set_socket(self, sock):
        self.zmq_socket = sock

    def start(self):
        self.zmq_ctx = zmq.asyncio.Context.instance()
        self.zmq_main_task = asyncio.ensure_future(self.run(), loop=self.loop)
        self.zmq_tasks = {}

    def stop(self):
        if self.zmq_main_task is not None and not self.zmq_main_task.done():
            self.zmq_main_task.cancel()
        for task in self.zmq_tasks.values():
            task.cancel()

    async def run(self):
        with self.zmq_ctx.socket(zmq.ROUTER) as sock:
            self._port = sock.bind_to_random_port('tcp://*')
            self.set_socket(sock)
            while True:
                addr, mtype, msgID, msg = await sock.recv_multipart()
                if mtype == RPC_REQUEST:
                    self.on_request(addr, msgID, msg)


class ZMQRPCCallable:
    def __init__(self, name, owner):
        self.name = name
        self.owner = owner

    def __call__(self, *args, **kw):
        return self.owner.performMethod(self.name, *args, **kw)

    def __getattr__(self, name):
        return ZMQRPCCallable(f"{self.name}.{name}", self.owner)


class ZMQClient(RPCClientMixin):
    def __init__(self, addr, timeout=1, loop=None):
        self._loop = asyncio.get_event_loop() if loop is None else loop
        self.set_timeout(timeout)
        self.addr = addr
        self._ctx = zmq.asyncio.Context.instance()
        self.zmq_socket = self._ctx.socket(zmq.DEALER)
        self.zmq_socket.connect(self.addr)
        self.main_task = asyncio.ensure_future(self.run(), loop=self.loop)

    def __del__(self):
        self.zmq_socket.close()
        self.close()
        self.main_task.cancel()

    @property
    def loop(self):
        return self._loop

    async def ping(self, timeout=1):
        return await super().ping(self.addr, timeout=timeout)

    async def send_msg(self, addr, mtype, msgID, msg):
        await self.zmq_socket.send_multipart([mtype, msgID, msg])

    async def run(self):
        while True:
            mtype, msgID, msg = await self.zmq_socket.recv_multipart()
            if mtype == RPC_RESPONSE:
                self.on_response(msgID, msg)

    def performMethod(self, name, *args, **kw):
        return self.callRemoteMethod(self.addr, name, *args, **kw)

    def __getattr__(self, name):
        return ZMQRPCCallable(name, self)
