import asyncio
import functools
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable

import zmq
import zmq.asyncio
from qulab.exceptions import (QuLabRPCError, QuLabRPCServerError,
                              QuLabRPCTimeout)
from qulab.serialize import pack, unpack
from qulab.utils import acceptArg, randomID

log = logging.getLogger(__name__)  # pylint: disable=invalid-name

# message type

RPC_REQUEST = b'\x01'
RPC_RESPONSE = b'\x02'
RPC_PING = b'\x03'
RPC_PONG = b'\x04'
RPC_CANCEL = b'\x05'
RPC_SHUTDOWN = b'\x06'


class RPCMixin(ABC):
    __pending = None
    __tasks = None

    @property
    def pending(self):
        if self.__pending is None:
            self.__pending = {}
        return self.__pending

    @property
    def tasks(self):
        if self.__tasks is None:
            self.__tasks = {}
        return self.__tasks

    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        self.stop()
        for task in self.tasks.values():
            try:
                task.cancel()
            finally:
                pass
        for fut, timeout in self.pending.values():
            try:
                fut.cancel()
                timeout.cancel()
            finally:
                pass

    def createTask(self, msgID, coro, timeout=0):
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

    def createPending(self, addr, msgID, timeout=1, cancelRemote=True):
        """
        Create a future for request, wait response before timeout.
        """
        fut = self.loop.create_future()
        self.pending[msgID] = (fut,
                               self.loop.call_later(timeout,
                                                    self.cancelPending, addr,
                                                    msgID, cancelRemote))
        return fut

    def cancelPending(self, addr, msgID, cancelRemote):
        """
        Give up when request timeout and try to cancel remote task.
        """
        fut, timeout = self.pending[msgID]
        if cancelRemote:
            self.cancelRemoteTask(addr, msgID)
        fut.set_exception(QuLabRPCTimeout('Time out.'))
        del self.pending[msgID]

    def cancelRemoteTask(self, addr, msgID):
        """
        Try to cancel remote task.
        """
        asyncio.ensure_future(self.sendto(RPC_CANCEL + msgID, addr),
                              loop=self.loop)

    @property
    @abstractmethod
    def loop(self):
        """
        Event loop.
        """

    @abstractmethod
    async def sendto(self, data, address):
        """
        Send message to address.
        """

    __rpc_handlers = {
        RPC_PING: 'on_ping',
        RPC_PONG: 'on_pong',
        RPC_REQUEST: 'on_request',
        RPC_RESPONSE: 'on_response',
        RPC_CANCEL: 'on_cancel',
        RPC_SHUTDOWN: 'on_shutdown',
    }

    def handle(self, source, data):
        """
        Handle received data.

        Should be called whenever received data from outside.
        """
        msg_type, data = data[:1], data[1:]
        log.debug(f'received request {msg_type} from {source}')
        handler = self.__rpc_handlers.get(msg_type, None)
        if handler is not None:
            getattr(self, handler)(source, data)

    async def ping(self, addr, timeout=1):
        await self.sendto(RPC_PING, addr)
        fut = self.createPending(addr, addr, timeout, False)
        try:
            return await fut
        except QuLabRPCTimeout:
            return False

    async def pong(self, addr):
        await self.sendto(RPC_PONG, addr)

    async def request(self, address, msgID, msg):
        log.debug(f'send request {address}, {msgID.hex()}, {msg}')
        await self.sendto(RPC_REQUEST + msgID + msg, address)

    async def response(self, address, msgID, msg):
        log.debug(f'send response {address}, {msgID.hex()}, {msg}')
        await self.sendto(RPC_RESPONSE + msgID + msg, address)

    async def shutdown(self, address):
        await self.sendto(RPC_SHUTDOWN, address)

    def on_request(self, source, data):
        """
        Handle request.

        Overwrite this method on server.
        """

    def on_response(self, source, data):
        """
        Handle response.

        Overwrite this method on client.
        """

    def on_ping(self, source, data):
        log.debug(f"received ping from {source}")
        asyncio.ensure_future(self.pong(source), loop=self.loop)

    def on_pong(self, source, data):
        log.debug(f"received pong from {source}")
        if source in self.pending:
            fut, timeout = self.pending[source]
            timeout.cancel()
            fut.set_result(True)
            del self.pending[msgID]

    def on_cancel(self, source, data):
        msgID = data[:20]
        self.cancelTask(msgID)

    def on_shutdown(self, source, data):
        if self.is_admin(source, data):
            raise SystemExit(0)

    def is_admin(self, source, data):
        return True


class RPCClientMixin(RPCMixin):
    _client_defualt_timeout = 1

    def set_timeout(self, timeout=1):
        self._client_defualt_timeout = timeout

    def remoteCall(self, addr, methodNane, args=(), kw=None):
        if kw is None:
            kw = {}
        if 'timeout' in kw:
            timeout = kw['timeout']
        else:
            timeout = self._client_defualt_timeout
        msg = pack((methodNane, args, kw))
        msgID = randomID()
        asyncio.ensure_future(self.request(addr, msgID, msg), loop=self.loop)
        return self.createPending(addr, msgID, timeout)

    def on_response(self, source, data):
        """
        Client side.
        """
        msgID, msg = data[:20], data[20:]
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
    def _unpack_request(self, msg):
        try:
            method, args, kw = unpack(msg)
        except:
            raise QuLabRPCError("Could not read packet: %r" % msg)
        return method, args, kw

    @abstractmethod
    def getRequestHandler(self, methodNane, source, msgID):
        """
        Get suitable handler for request.

        You should implement this method yourself.
        """

    def on_request(self, source, data):
        """
        Received a request from source.
        """
        msgID, msg = data[:20], data[20:]
        try:
            method, args, kw = self._unpack_request(msg)
            self.createTask(msgID,
                            self.handle_request(source, msgID, method, *args,
                                                **kw),
                            timeout=kw.get('timeout', 0))
        except Exception as e:
            self.response(source, msgID, pack(QuLabRPCServerError(*e.args)))

    async def handle_request(self, source, msgID, method, *args, **kw):
        """
        Handle a request from source.
        """
        try:
            func = self.getRequestHandler(method, source=source, msgID=msgID)
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
        await self.response(source, msgID, msg)


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

    async def sendto(self, data, address):
        self.zmq_socket.send_multipart([address, data])

    def getRequestHandler(self, methodNane, **kw):
        path = methodNane.split('.')
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
        super().start()
        self.zmq_ctx = zmq.asyncio.Context.instance()
        self.zmq_main_task = asyncio.ensure_future(self.run(), loop=self.loop)

    def stop(self):
        if self.zmq_main_task is not None and not self.zmq_main_task.done():
            self.zmq_main_task.cancel()
        super().stop()

    async def run(self):
        with self.zmq_ctx.socket(zmq.ROUTER, io_loop=self._loop) as sock:
            sock.setsockopt(zmq.LINGER, 0)
            self._port = sock.bind_to_random_port('tcp://*')
            self.set_socket(sock)
            while True:
                addr, data = await sock.recv_multipart()
                log.debug('received data from %r' % addr.hex())
                self.handle(addr, data)


class ZMQRPCCallable:
    def __init__(self, methodNane, owner):
        self.methodNane = methodNane
        self.owner = owner

    def __call__(self, *args, **kw):
        return self.owner.performMethod(self.methodNane, args, kw)

    def __getattr__(self, name):
        return ZMQRPCCallable(f"{self.methodNane}.{name}", self.owner)


class ZMQClient(RPCClientMixin):
    def __init__(self, addr, timeout=1, loop=None):
        self._loop = asyncio.get_event_loop() if loop is None else loop
        self.set_timeout(timeout)
        self.addr = addr
        self._ctx = zmq.asyncio.Context()
        self.zmq_socket = self._ctx.socket(zmq.DEALER, io_loop=self._loop)
        self.zmq_socket.setsockopt(zmq.LINGER, 0)
        self.zmq_socket.connect(self.addr)
        self.zmq_main_task = asyncio.ensure_future(self.run(), loop=self.loop)

    def __del__(self):
        self.zmq_socket.close()
        self.close()
        self.zmq_main_task.cancel()

    @property
    def loop(self):
        return self._loop

    async def ping(self, timeout=1):
        return await super().ping(self.addr, timeout=timeout)

    async def sendto(self, data, addr):
        await self.zmq_socket.send_multipart([data])

    async def run(self):
        while True:
            data, = await self.zmq_socket.recv_multipart()
            self.handle(self.addr, data)

    def performMethod(self, methodNane, args, kw):
        return self.remoteCall(self.addr, methodNane, args, kw)

    def __getattr__(self, name):
        return ZMQRPCCallable(name, self)
