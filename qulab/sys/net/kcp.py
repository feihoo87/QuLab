import asyncio
import time

from . import _kcp


class KCPConnection():

    def __init__(self,
                 address: tuple[str, int],
                 transport: asyncio.DatagramTransport,
                 conv: int,
                 nodelay: bool = True,
                 interval: int = 20,
                 resend: int = 2,
                 nc: bool = True):
        self._kcp = _kcp.kcp_create(conv, self)
        _kcp.kcp_nodelay(self._kcp, int(nodelay), interval, resend, int(nc))
        self.interval = interval
        self.address = address
        self.transport = transport
        self.last_active = time.time()
        self.send_queue = asyncio.Queue()
        self.recv_queue = asyncio.Queue()
        self.fut = asyncio.create_task(self.run())

    def __del__(self):
        try:
            self.fut.cancel()
        except:
            pass
        _kcp.kcp_release(self._kcp)

    def output(self, msg):
        self.transport.sendto(msg, self.address)

    def send(self, buff):
        self.last_active = time.time()
        self.send_queue.put_nowait(buff)

    def _send(self, buff):
        return _kcp.kcp_send(self._kcp, buff)

    async def recv(self):
        return await self.recv_queue.get()

    def recv_nowait(self):
        self.flush()
        try:
            return self.recv_queue.get_nowait()
        except:
            return None

    def _recv(self):
        return _kcp.kcp_recv(self._kcp)

    def _update(self):
        _kcp.kcp_update(self._kcp, self.clock())

    def check(self):
        current = self.clock()
        return _kcp.kcp_check(self._kcp, current) - current

    def clock(self):
        return (time.monotonic_ns() // 1000_000) & 0x7fffffff

    def input(self, buff):
        self.last_active = time.time()
        return _kcp.kcp_input(self._kcp, buff)

    async def update(self):
        while True:
            await asyncio.sleep(self.check() / 1000)
            self._update()

    async def sync(self):
        while True:
            await asyncio.sleep(self.interval / 1000)
            self.flush()

    async def run(self):
        await asyncio.gather(self.update(), self.sync())

    def flush(self):
        while True:
            buff = self._recv()
            if isinstance(buff, int):
                break
            self.recv_queue.put_nowait(buff)
        while True:
            try:
                buff = self.send_queue.get_nowait()
                if self._send(buff) < 0:
                    self.send_queue.put_nowait(buff)
                    break
            except asyncio.QueueEmpty:
                break

        return True


class KCPProtocol(asyncio.DatagramProtocol):

    def __init__(self,
                 conv: int,
                 ttl: int = 3600,
                 nodelay: bool = True,
                 interval: int = 20,
                 resend: int = 2,
                 nc: bool = True):
        self.ttl = ttl
        self.conv = conv
        self.nodelay = nodelay
        self.interval = interval
        self.resend = resend
        self.nc = nc
        self.transport = None
        self.connections = {}
        self.autoclean_loop: asyncio.Future = None
        self.clean()

    def connection_lost(self, exc):
        self.autoclean_loop.cancel()
        for address in self.connections:
            del self.connections[address]

    def connection_made(self, transport):
        self.transport = transport

    def get_connection(self, address):
        if address not in self.connections:
            self.connections[address] = KCPConnection(address, self.transport,
                                                      self.conv, self.nodelay,
                                                      self.interval,
                                                      self.resend, self.nc)
        self.connections[address].last_recv = time.time()
        return self.connections[address]

    def datagram_received(self, datagram, address):
        self.get_connection(address).input(datagram)

    def sendto(self, msg, address):
        self.get_connection(address).send(msg)

    def recvfrom(self):
        for address, conn in list(self.connections.items()):
            buff = conn.recv_nowait()
            if buff:
                return buff, address

    def clean(self):
        current = time.time()
        dead = []
        for address, conn in list(self.connections.items()):
            if current - conn.last_active > self.ttl:
                dead.append(address)
        for address in dead:
            del self.connections[address]
        loop = asyncio.get_running_loop()
        self.autoclean_loop = loop.call_later(10, self.clean)


async def listen(address: tuple[str, int],
                 conv: int = 1234,
                 ttl: int = 3600,
                 nodelay: bool = True,
                 interval: int = 20,
                 resend: int = 2,
                 nc: bool = True):
    """
    Listen on a UDP address and return a KCPProtocol instance.

    Args:
        ttl (int): The connection TTL (in second).
        address (ip, port): The address to listen on.
        conv (int): The conversation ID.
        nodelay (bool): Whether to enable nodelay mode.
        interval (int): The internal update interval (in millisecond).
        resend (int): The number of times to resend unacknowledged packets.
        nc (bool): Whether to enable congestion control.

    Returns:
        A KCPProtocol instance.
    """

    def protocol_factory():
        return KCPProtocol(conv, ttl, nodelay, interval, resend, nc)

    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        protocol_factory, local_addr=address)
    return protocol