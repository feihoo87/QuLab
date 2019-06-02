import asyncio
import functools
import logging
import random

from qulab.dht.node import Node
from qulab.dht.routing import RoutingTable
from qulab.dht.utils import digest
from qulab.rpc import RPC_REQUEST, RPC_RESPONSE, RPCClientMixin, RPCServerMixin
from qulab.serialize import pack, unpack

log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class KademliaProtocol(asyncio.DatagramProtocol, RPCClientMixin,
                       RPCServerMixin):
    def __init__(self, source_node, storage, ksize, waitTimeout=0.1, loop=None):
        """
        @param waitTimeout: Consider it a connetion failure if no response
        within this time window.
        """
        self.set_timeout(waitTimeout)
        self.transport = None
        self._loop = loop or asyncio.get_running_loop()
        self.router = RoutingTable(self, ksize, source_node, loop=self._loop)
        self.storage = storage
        self.source_node = source_node

    @property
    def loop(self):
        return self._loop

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        log.debug("received datagram from %s", addr)
        self.handle(addr, data)

    async def sendto(self, data, address):
        log.debug(f'send data to {address}.')
        self.transport.sendto(data, address)

    def getRequestHandler(self, name, source, msgID):
        f = getattr(self, "rpc_%s" % name, None)
        if f is None or not callable(f):
            msgargs = (self.__class__.__name__, name)
            log.warning(
                "%s has no callable method "
                "rpc_%s; ignoring request", *msgargs)
            return
        return functools.partial(f, source)

    def get_refresh_ids(self):
        """
        Get ids to search for to keep old buckets up to date.
        """
        ids = []
        for bucket in self.router.lonely_buckets():
            rid = random.randint(*bucket.range).to_bytes(20, byteorder='big')
            ids.append(rid)
        return ids

    def rpc_stun(self, sender):  # pylint: disable=no-self-use
        return sender

    def rpc_ping(self, sender, nodeid):
        source = Node(nodeid, sender[0], sender[1])
        self.welcome_if_new(source)
        return self.source_node.id

    def rpc_store(self, sender, nodeid, key, value):
        source = Node(nodeid, sender[0], sender[1])
        self.welcome_if_new(source)
        log.debug("got a store request from %s, storing '%s'='%s'", sender,
                  key.hex(), value)
        self.storage[key] = value
        return True

    def rpc_find_node(self, sender, nodeid, key):
        log.info("finding neighbors of %i in local table",
                 int(nodeid.hex(), 16))
        source = Node(nodeid, sender[0], sender[1])
        self.welcome_if_new(source)
        node = Node(key)
        neighbors = self.router.find_neighbors(node, exclude=source)
        return list(map(tuple, neighbors))

    def rpc_find_value(self, sender, nodeid, key):
        source = Node(nodeid, sender[0], sender[1])
        self.welcome_if_new(source)
        value = self.storage.get(key, None)
        if value is None:
            return self.rpc_find_node(sender, nodeid, key)
        return {'value': value}

    async def ping(self, addr, nodeid):
        """
        Overwrite ping.
        """
        return await self._remoteCall(addr, nodeid, name='ping')

    async def _call(self, node_to_ask, *args, name=None):
        address = (node_to_ask.ip, node_to_ask.port)
        if name in ['find_node', 'find_value']:
            node_to_find, = args
            args = (node_to_find.id, )
        log.debug(f'call_{name}, {address}, {args}')
        result = await self._remoteCall(address,
                                        self.source_node.id,
                                        *args,
                                        name=name)
        return self.handle_call_response(result, node_to_ask)

    async def _remoteCall(self, addr, *args, name=None):
        """
        Call `rpc_{name}` method on `addr`. Return `received response` and result.
        """
        log.debug(f"call remote `{name}` {addr}, {args}")
        try:
            return (True, await self.remoteCall(addr, name, args))
        except:
            return (False, None)

    def __getattr__(self, name):
        if name.startswith('call_'):
            return functools.partial(self._call, name=name[5:])
        else:
            return functools.partial(self._remoteCall, name=name)

    def welcome_if_new(self, node):
        """
        Given a new node, send it all the keys/values it should be storing,
        then add it to the routing table.
        @param node: A new node that just joined (or that we just found out
        about).
        Process:
        For each key in storage, get k closest nodes.  If newnode is closer
        than the furtherst in that list, and the node for this server
        is closer than the closest in that list, then store the key/value
        on the new node (per section 2.5 of the paper)
        """
        if not self.router.is_new_node(node):
            return

        log.info("never seen %s before, adding to router", node)
        for key, value in self.storage:
            keynode = Node(digest(key))
            neighbors = self.router.find_neighbors(keynode)
            if neighbors:
                last = neighbors[-1].distance_to(keynode)
                new_node_close = node.distance_to(keynode) < last
                first = neighbors[0].distance_to(keynode)
                this_closest = self.source_node.distance_to(keynode) < first
            if not neighbors or (new_node_close and this_closest):
                asyncio.ensure_future(self.call_store(node, key, value), loop=self.loop)
        self.router.add_contact(node)

    def handle_call_response(self, result, node):
        """
        If we get a response, add the node to the routing table.  If
        we get no response, make sure it's removed from the routing table.
        """
        if not result[0]:
            log.warning("no response from %s, removing from router", node)
            self.router.remove_contact(node)
            return result

        log.info("got successful response from %s", node)
        self.welcome_if_new(node)
        return result
