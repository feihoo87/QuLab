from __future__ import annotations

import asyncio
import heapq
import logging
import os
import pickle
import random
import re
import secrets
import time
import uuid
from abc import ABC, abstractmethod
from base64 import b64encode
from collections import Counter, OrderedDict
from hashlib import sha1
from itertools import chain
from operator import itemgetter
from typing import Any, Coroutine, NamedTuple

import msgpack

log = logging.getLogger(__name__)


class Value(NamedTuple):
    value: Any
    ttl: float | None
    ts: float

    def outdated(self):
        return self.ttl is not None and self.ttl < time.time() - self.ts

    def __repr__(self):
        fmt = "%a, %d %b %Y %H:%M:%S"
        mt = time.strftime(fmt, time.localtime(self.ts))
        return f"{self.value!r}, ttl={self.ttl}, last modified at {mt}"


class IStorage(ABC):
    """
    Local storage for this node.
    IStorage implementations of get must return the same type as put in by set
    """

    @abstractmethod
    def __setitem__(self, key: bytes, value):
        """
        Set a key to the given value.
        """

    @abstractmethod
    def __getitem__(self, key: bytes):
        """
        Get the given key.  If item doesn't exist, return None.
        """

    @abstractmethod
    def get(self, key: bytes, default=None):
        """
        Get given key.  If not found, return default.
        """

    @abstractmethod
    def set(self, key: bytes, value, ttl: float = 0):
        """
        Set a key to the given value.
        """

    @abstractmethod
    def iter_older_than(self, seconds_old: float):
        """
        Return the an iterator over (key, value) tuples for items older
        than the given secondsOld.
        """

    @abstractmethod
    def __iter__(self):
        """
        Get the iterator for this storage, should yield tuple of (key, value)
        """


class ForgetfulStorage(IStorage):

    def __init__(self, ttl: float = 604800):
        self._storage: dict[bytes, Value] = {}
        self.ttl: float = ttl

    def get(self, key: bytes):
        if key not in self._storage:
            return None
        value = self._storage[key]
        if value.outdated():
            del self._storage[key]
            return None
        else:
            return value.value

    def set(self, key: bytes, value, ttl: float | None = None):
        if ttl is None:
            ttl = self.ttl
        self._storage[key] = Value(value, ttl, time.time())

    def __iter(self):
        for key, value in list(self._storage.items()):
            if value.outdated():
                del self._storage[key]
                continue
            yield key, value

    def cull(self):
        for key, value in self.__iter():
            if value.outdated():
                del self._storage[key]
                continue

    def __repr__(self):
        self.cull()
        return repr(self._storage)

    def __contains__(self, key: bytes):
        if key in self._storage:
            value = self._storage[key]
            if value.outdated():
                del self._storage[key]
                return False
            else:
                return True
        else:
            return False

    def __setitem__(self, key: bytes, value):
        self.set(key, value, ttl=self.ttl)

    def __getitem__(self, key: bytes):
        return self.get(key)

    def __iter__(self):
        for key, value in self.__iter():
            yield key, value.value

    def expire(self, key: bytes, ttl: float):
        if key in self._storage:
            value = self._storage[key]
            self._storage[key] = Value(value.value, ttl, time.time())

    def exists(self, key: bytes):
        return self.__contains__(key)

    def keys(self, pattern="*"):
        return [key for key in self.scan_iter(pattern)]

    def scan_iter(self, pattern="*"):
        prog = re.compile(pattern.replace("*", ".*"))
        for key, _ in self.__iter():
            if prog.match(key):
                yield key

    def iter_older_than(self, t: float):
        for key, value in self.__iter():
            if time.time() - value.ts >= t:
                yield key, value.value


async def gather_dict(dic: dict[bytes, Coroutine]):
    cors = list(dic.values())
    results = await asyncio.gather(*cors)
    return dict(zip(dic.keys(), results))


def digest(string: str | bytes) -> bytes:
    if not isinstance(string, bytes):
        string = str(string).encode('utf8')
    return sha1(string).digest()


def shared_prefix(args):
    """
    Find the shared prefix between the strings.
    For instance:
        sharedPrefix(['blahblah', 'blahwhat'])
    returns 'blah'.
    """
    i = 0
    while i < min(map(len, args)):
        if len(set(map(itemgetter(i), args))) != 1:
            break
        i += 1
    return args[0][:i]


def bytes_to_bit_string(bites):
    bits = [bin(bite)[2:].rjust(8, '0') for bite in bites]
    return "".join(bits)


class Node:
    """
    Simple object to encapsulate the concept of a Node (minimally an ID, but
    also possibly an IP and port if this represents a node on the network).
    This class should generally not be instantiated directly, as it is a low
    level construct mostly used by the router.
    """
    __slots__ = ('id', 'ip', 'port', 'long_id')

    def __init__(self, node_id: bytes, ip=None, port=None):
        """
        Create a Node instance.
        Args:
            node_id (int): A value between 0 and 2^160
            ip (string): Optional IP address where this Node lives
            port (int): Optional port for this Node (set when IP is set)
        """
        self.id = node_id  # pylint: disable=invalid-name
        self.ip = ip  # pylint: disable=invalid-name
        self.port = port
        self.long_id = int(node_id.hex(), 16)

    def same_home_as(self, node):
        return self.ip == node.ip and self.port == node.port

    def distance_to(self, node):
        """
        Get the distance between this node and another.
        """
        return self.long_id ^ node.long_id

    def __iter__(self):
        """
        Enables use of Node as a tuple - i.e., tuple(node) works.
        """
        return iter([self.id, self.ip, self.port])

    def __repr__(self):
        return repr([self.long_id, self.ip, self.port])

    def __str__(self):
        return "%s:%s" % (self.ip, str(self.port))


class NodeHeap:
    """
    A heap of nodes ordered by distance to a given node.
    """

    def __init__(self, node: Node, maxsize: int):
        """
        Constructor.
        @param node: The node to measure all distnaces from.
        @param maxsize: The maximum size that this heap can grow to.
        """
        self.node = node
        self.heap = []
        self.contacted = set()
        self.maxsize = maxsize

    def remove(self, peers):
        """
        Remove a list of peer ids from this heap.  Note that while this
        heap retains a constant visible size (based on the iterator), it's
        actual size may be quite a bit larger than what's exposed.  Therefore,
        removal of nodes may not change the visible size as previously added
        nodes suddenly become visible.
        """
        peers = set(peers)
        if not peers:
            return
        nheap = []
        for distance, node in self.heap:
            if node.id not in peers:
                heapq.heappush(nheap, (distance, node))
        self.heap = nheap

    def get_node(self, node_id):
        for _, node in self.heap:
            if node.id == node_id:
                return node
        return None

    def have_contacted_all(self):
        return len(self.get_uncontacted()) == 0

    def get_ids(self):
        return [n.id for n in self]

    def mark_contacted(self, node):
        self.contacted.add(node.id)

    def popleft(self):
        return heapq.heappop(self.heap)[1] if self else None

    def push(self, nodes):
        """
        Push nodes onto heap.
        @param nodes: This can be a single item or a C{list}.
        """
        if not isinstance(nodes, list):
            nodes = [nodes]

        for node in nodes:
            if node not in self:
                distance = self.node.distance_to(node)
                heapq.heappush(self.heap, (distance, node))

    def __len__(self):
        return min(len(self.heap), self.maxsize)

    def __iter__(self):
        nodes = heapq.nsmallest(self.maxsize, self.heap)
        return iter(map(itemgetter(1), nodes))

    def __contains__(self, node):
        for _, other in self.heap:
            if node.id == other.id:
                return True
        return False

    def get_uncontacted(self):
        return [n for n in self if n.id not in self.contacted]


class KBucket:

    def __init__(self, rangeLower, rangeUpper, ksize, replacementNodeFactor=5):
        self.range = (rangeLower, rangeUpper)
        self.nodes = OrderedDict()
        self.replacement_nodes = OrderedDict()
        self.touch_last_updated()
        self.ksize = ksize
        self.max_replacement_nodes = self.ksize * replacementNodeFactor

    def touch_last_updated(self):
        self.last_updated = time.monotonic()

    def get_nodes(self):
        return list(self.nodes.values())

    def split(self):
        midpoint = (self.range[0] + self.range[1]) // 2
        one = KBucket(self.range[0], midpoint, self.ksize)
        two = KBucket(midpoint + 1, self.range[1], self.ksize)
        nodes = chain(self.nodes.values(), self.replacement_nodes.values())
        for node in nodes:
            bucket = one if node.long_id <= midpoint else two
            bucket.add_node(node)

        return (one, two)

    def remove_node(self, node):
        if node.id in self.replacement_nodes:
            del self.replacement_nodes[node.id]

        if node.id in self.nodes:
            del self.nodes[node.id]

            if self.replacement_nodes:
                newnode_id, newnode = self.replacement_nodes.popitem()
                self.nodes[newnode_id] = newnode

    def has_in_range(self, node):
        return self.range[0] <= node.long_id <= self.range[1]

    def is_new_node(self, node):
        return node.id not in self.nodes

    def add_node(self, node):
        """
        Add a C{Node} to the C{KBucket}.  Return True if successful,
        False if the bucket is full.
        If the bucket is full, keep track of node in a replacement list,
        per section 4.1 of the paper.
        """
        if node.id in self.nodes:
            del self.nodes[node.id]
            self.nodes[node.id] = node
        elif len(self) < self.ksize:
            self.nodes[node.id] = node
        else:
            if node.id in self.replacement_nodes:
                del self.replacement_nodes[node.id]
            self.replacement_nodes[node.id] = node
            while len(self.replacement_nodes) > self.max_replacement_nodes:
                self.replacement_nodes.popitem(last=False)
            return False
        return True

    def depth(self):
        vals = self.nodes.values()
        sprefix = shared_prefix([bytes_to_bit_string(n.id) for n in vals])
        return len(sprefix)

    def head(self):
        return list(self.nodes.values())[0]

    def __getitem__(self, node_id):
        return self.nodes.get(node_id, None)

    def __len__(self):
        return len(self.nodes)


class TableTraverser:

    def __init__(self, table, startNode):
        index = table.get_bucket_for(startNode)
        table.buckets[index].touch_last_updated()
        self.current_nodes = table.buckets[index].get_nodes()
        self.left_buckets = table.buckets[:index]
        self.right_buckets = table.buckets[(index + 1):]
        self.left = True

    def __iter__(self):
        return self

    def __next__(self):
        """
        Pop an item from the left subtree, then right, then left, etc.
        """
        if self.current_nodes:
            return self.current_nodes.pop()

        if self.left and self.left_buckets:
            self.current_nodes = self.left_buckets.pop().get_nodes()
            self.left = False
            return next(self)

        if self.right_buckets:
            self.current_nodes = self.right_buckets.pop(0).get_nodes()
            self.left = True
            return next(self)

        raise StopIteration


class RoutingTable:

    def __init__(self, protocol, ksize, node):
        """
        @param node: The node that represents this server.  It won't
        be added to the routing table, but will be needed later to
        determine which buckets to split or not.
        """
        self.node = node
        self.protocol = protocol
        self.ksize = ksize
        self.flush()

    def flush(self):
        self.buckets: list[KBucket] = [KBucket(0, 2**160, self.ksize)]

    def split_bucket(self, index: int):
        one, two = self.buckets[index].split()
        self.buckets[index] = one
        self.buckets.insert(index + 1, two)

    def lonely_buckets(self):
        """
        Get all of the buckets that haven't been updated in over
        an hour.
        """
        hrago = time.monotonic() - 3600
        return [b for b in self.buckets if b.last_updated < hrago]

    def remove_contact(self, node):
        index = self.get_bucket_for(node)
        self.buckets[index].remove_node(node)

    def is_new_node(self, node):
        index = self.get_bucket_for(node)
        return self.buckets[index].is_new_node(node)

    def add_contact(self, node):
        index = self.get_bucket_for(node)
        bucket = self.buckets[index]

        # this will succeed unless the bucket is full
        if bucket.add_node(node):
            return

        # Per section 4.2 of paper, split if the bucket has the node
        # in its range or if the depth is not congruent to 0 mod 5
        if bucket.has_in_range(self.node) or bucket.depth() % 5 != 0:
            self.split_bucket(index)
            self.add_contact(node)
        else:
            asyncio.ensure_future(self.protocol.call_ping(bucket.head()))

    def get_bucket_for(self, node):
        """
        Get the index of the bucket that the given node would fall into.
        """
        for index, bucket in enumerate(self.buckets):
            if node.long_id < bucket.range[1]:
                return index
        # we should never be here, but make linter happy
        return None

    def find_neighbors(self, node, k=None, exclude=None):
        k = k or self.ksize
        nodes = []
        for neighbor in TableTraverser(self, node):
            notexcluded = exclude is None or not neighbor.same_home_as(exclude)
            if neighbor.id != node.id and notexcluded:
                heapq.heappush(nodes, (node.distance_to(neighbor), neighbor))
            if len(nodes) == k:
                break

        return list(map(itemgetter(1), heapq.nsmallest(k, nodes)))


class SpiderCrawl:
    """
    Crawl the network and look for given 160-bit keys.
    """

    def __init__(self, protocol: KademliaProtocol, node, peers, ksize, alpha):
        """
        Create a new C{SpiderCrawl}er.
        Args:
            protocol: A :class:`~kademlia.protocol.KademliaProtocol` instance.
            node: A :class:`~kademlia.node.Node` representing the key we're
                  looking for
            peers: A list of :class:`~kademlia.node.Node` instances that
                   provide the entry point for the network
            ksize: The value for k based on the paper
            alpha: The value for alpha based on the paper
        """
        self.protocol = protocol
        self.ksize = ksize
        self.alpha = alpha
        self.node = node
        self.nearest = NodeHeap(self.node, self.ksize)
        self.last_ids_crawled = []
        log.info("creating spider with peers: %s", peers)
        self.nearest.push(peers)

    async def _find(self, rpcmethod):
        """
        Get either a value or list of nodes.
        Args:
            rpcmethod: The protocol's callfindValue or call_find_node.
        The process:
          1. calls find_* to current ALPHA nearest not already queried nodes,
             adding results to current nearest list of k nodes.
          2. current nearest list needs to keep track of who has been queried
             already sort by nearest, keep KSIZE
          3. if list is same as last time, next call should be to everyone not
             yet queried
          4. repeat, unless nearest list has all been queried, then ur done
        """
        log.info("crawling network with nearest: %s", str(tuple(self.nearest)))
        count = self.alpha
        if self.nearest.get_ids() == self.last_ids_crawled:
            count = len(self.nearest)
        self.last_ids_crawled = self.nearest.get_ids()

        dicts = {}
        for peer in self.nearest.get_uncontacted()[:count]:
            dicts[peer.id] = rpcmethod(peer, self.node)
            self.nearest.mark_contacted(peer)
        found = await gather_dict(dicts)
        return await self._nodes_found(found)

    async def _nodes_found(self, responses):
        raise NotImplementedError


class ValueSpiderCrawl(SpiderCrawl):

    def __init__(self, protocol: KademliaProtocol, node, peers, ksize, alpha):
        SpiderCrawl.__init__(self, protocol, node, peers, ksize, alpha)
        # keep track of the single nearest node without value - per
        # section 2.3 so we can set the key there if found
        self.nearest_without_value = NodeHeap(self.node, 1)

    async def find(self):
        """
        Find either the closest nodes or the value requested.
        """
        return await self._find(self.protocol.call_find_value)

    async def _nodes_found(self, responses):
        """
        Handle the result of an iteration in _find.
        """
        toremove = []
        found_values = []
        for peerid, response in responses.items():
            response = RPCFindResponse(response)
            if not response.happened():
                toremove.append(peerid)
            elif response.has_value():
                found_values.append(response.get_value())
            else:
                peer = self.nearest.get_node(peerid)
                self.nearest_without_value.push(peer)
                self.nearest.push(response.get_node_list())
        self.nearest.remove(toremove)

        if found_values:
            return await self._handle_found_values(found_values)
        if self.nearest.have_contacted_all():
            # not found!
            return None
        return await self.find()

    async def _handle_found_values(self, values):
        """
        We got some values!  Exciting.  But let's make sure
        they're all the same or freak out a little bit.  Also,
        make sure we tell the nearest node that *didn't* have
        the value to store it.
        """
        value_counts = Counter(values)
        if len(value_counts) != 1:
            log.warning("Got multiple values for key %i: %s",
                        self.node.long_id, str(values))
        value = value_counts.most_common(1)[0][0]

        peer = self.nearest_without_value.popleft()
        if peer:
            await self.protocol.call_store(peer, self.node.id, value)
        return value


class NodeSpiderCrawl(SpiderCrawl):

    async def find(self):
        """
        Find the closest nodes.
        """
        return await self._find(self.protocol.call_find_node)

    async def _nodes_found(self, responses):
        """
        Handle the result of an iteration in _find.
        """
        toremove = []
        for peerid, response in responses.items():
            response = RPCFindResponse(response)
            if not response.happened():
                toremove.append(peerid)
            else:
                self.nearest.push(response.get_node_list())
        self.nearest.remove(toremove)

        if self.nearest.have_contacted_all():
            return list(self.nearest)
        return await self.find()


class RPCFindResponse:

    def __init__(self, response):
        """
        A wrapper for the result of a RPC find.
        Args:
            response: This will be a tuple of (<response received>, <value>)
                      where <value> will be a list of tuples if not found or
                      a dictionary of {'value': v} where v is the value desired
        """
        self.response = response

    def happened(self):
        """
        Did the other host actually respond?
        """
        return self.response[0]

    def has_value(self):
        return isinstance(self.response[1], dict)

    def get_value(self):
        return self.response[1]['value']

    def get_node_list(self):
        """
        Get the node list in the response.  If there's no value, this should
        be set.
        """
        nodelist = self.response[1] or []
        return [Node(*nodeple) for nodeple in nodelist]


class MalformedMessage(Exception):
    """
    Message does not contain what is expected.
    """


class RPCProtocol(asyncio.DatagramProtocol):

    def __init__(self, wait_timeout: float = 5):
        self._timeout = wait_timeout
        self._outstanding: dict[bytes, tuple[asyncio.Future,
                                             asyncio.TimerHandle]] = {}
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, datagram, address):
        log.debug("received datagram from %s", address)
        if len(datagram) < 22:
            log.warning("received datagram too small from %s,"
                        " ignoring", address)
            return

        msg_id = datagram[1:21]
        data = msgpack.unpackb(datagram[21:])

        if datagram[:1] == b'\x00':
            # schedule accepting request and returning the result
            self.handle_request(msg_id, data, address)
        elif datagram[:1] == b'\x01':
            self.handle_response(msg_id, data, address)
        else:
            # otherwise, don't know the format, don't do anything
            log.debug("Received unknown message from %s, ignoring", address)

    def handle_response(self, msg_id, data, address):
        msgargs = (b64encode(msg_id), address)
        if msg_id not in self._outstanding:
            log.warning("received unknown message %s "
                        "from %s; ignoring", *msgargs)
            return
        log.debug("received response %s for message "
                  "id %s from %s", data, *msgargs)
        future, timeout = self._outstanding[msg_id]
        timeout.cancel()
        future.set_result((True, data))
        del self._outstanding[msg_id]

    def handle_request(self, msg_id, data, address):
        if not isinstance(data, list) or len(data) != 2:
            raise MalformedMessage("Could not read packet: %s" % data)
        funcname, args = data

        try:
            func = getattr(self, f"on_{funcname}")
        except AttributeError:
            msgargs = (self.__class__.__name__, funcname)
            log.warning("%s has no callable method "
                        "on_%s; ignoring request", *msgargs)
            return

        try:
            response = func(address, *args)
        except Exception as e:
            log.exception(e)

        log.debug("sending response %s for msg id %s to %s", response,
                  b64encode(msg_id), address)
        txdata = b'\x01' + msg_id + msgpack.packb(response)
        self.transport.sendto(txdata, address)

    def rpc_call(self, name, address, *args):
        msg_id = sha1(os.urandom(32)).digest()
        data = msgpack.packb([name, args])
        if len(data) > 8192:
            raise MalformedMessage("Total length of function "
                                   "name and arguments cannot exceed 8K")
        txdata = b'\x00' + msg_id + data
        log.debug("calling remote function %s on %s (msgid %s)", name, address,
                  b64encode(msg_id))
        self.transport.sendto(txdata, address)

        loop = asyncio.get_event_loop()
        if hasattr(loop, 'create_future'):
            future = loop.create_future()
        else:
            future = asyncio.Future()
        timeout = loop.call_later(self._timeout, self.rpc_cancel, msg_id)
        self._outstanding[msg_id] = (future, timeout)
        return future

    def rpc_cancel(self, msg_id):
        args = (b64encode(msg_id), self._timeout)
        log.error("Did not receive reply for msg "
                  "id %s within %i seconds", *args)
        self._outstanding[msg_id][0].set_result((False, None))
        del self._outstanding[msg_id]


class KademliaProtocol(RPCProtocol):

    def __init__(self, source_node, storage, ksize, wait_timeout=5):
        super().__init__(wait_timeout)
        self.router = RoutingTable(self, ksize, source_node)
        self.storage = storage
        self.source_node = source_node

    def get_refresh_ids(self):
        """
        Get ids to search for to keep old buckets up to date.
        """
        ids = []
        for bucket in self.router.lonely_buckets():
            rid = random.randint(*bucket.range).to_bytes(20, byteorder='big')
            ids.append(rid)
        return ids

    def on_ping(self, sender, nodeid):
        source = Node(nodeid, sender[0], sender[1])
        self.welcome_if_new(source)
        return self.source_node.id

    def on_store(self, sender, nodeid, key, value):
        source = Node(nodeid, sender[0], sender[1])
        self.welcome_if_new(source)
        log.debug("got a store request from %s, storing '%s'='%s'", sender,
                  key.hex(), value)
        self.storage[key] = value
        return True

    def on_find_node(self, sender, nodeid, key):
        log.info("finding neighbors of %i in local table",
                 int(nodeid.hex(), 16))
        source = Node(nodeid, sender[0], sender[1])
        self.welcome_if_new(source)
        node = Node(key)
        neighbors = self.router.find_neighbors(node, exclude=source)
        return list(map(tuple, neighbors))

    def on_find_value(self, sender, nodeid, key):
        source = Node(nodeid, sender[0], sender[1])
        self.welcome_if_new(source)
        value = self.storage.get(key)
        if value is None:
            return self.on_find_node(sender, nodeid, key)
        return {'value': value}

    async def ping(self, address, source_node_id):
        return await self.rpc_call('ping', address, source_node_id)

    async def store(self, address, source_node_id, key, value):
        return await self.rpc_call('store', address, source_node_id, key,
                                   value)

    async def find_node(self, address, source_node_id, node_to_find_id):
        return await self.rpc_call('find_node', address, source_node_id,
                                   node_to_find_id)

    async def find_value(self, address, source_node_id, node_to_find_id):
        return await self.rpc_call('find_value', address, source_node_id,
                                   node_to_find_id)

    async def call_find_node(self, node_to_ask, node_to_find):
        address = (node_to_ask.ip, node_to_ask.port)
        result = await self.find_node(address, self.source_node.id,
                                      node_to_find.id)
        return self.handle_rpc_result(result, node_to_ask)

    async def call_find_value(self, node_to_ask, node_to_find):
        address = (node_to_ask.ip, node_to_ask.port)
        result = await self.find_value(address, self.source_node.id,
                                       node_to_find.id)
        return self.handle_rpc_result(result, node_to_ask)

    async def call_ping(self, node_to_ask):
        address = (node_to_ask.ip, node_to_ask.port)
        result = await self.ping(address, self.source_node.id)
        return self.handle_rpc_result(result, node_to_ask)

    async def call_store(self, node_to_ask, key, value):
        address = (node_to_ask.ip, node_to_ask.port)
        result = await self.store(address, self.source_node.id, key, value)
        return self.handle_rpc_result(result, node_to_ask)

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
                asyncio.ensure_future(self.call_store(node, key, value))
        self.router.add_contact(node)

    def handle_rpc_result(self, result, node):
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


class Server:
    """
    High level view of a node instance.  This is the object that should be
    created to start listening as an active node on the network.
    """

    protocol_class = KademliaProtocol

    def __init__(self, ksize=20, alpha=3, node_id=None, storage=None):
        """
        Create a server instance.  This will start listening on the given port.
        Args:
            ksize (int): The k parameter from the paper
            alpha (int): The alpha parameter from the paper
            node_id: The id for this node on the network.
            storage: An instance that implements the interface
                     :class:`~kademlia.storage.IStorage`
        """
        self.ksize = ksize
        self.alpha = alpha
        self.storage = storage or ForgetfulStorage()
        self.node = Node(node_id
                         or uuid.uuid1().bytes[4:] + secrets.token_bytes(8))
        self.transport = None
        self.protocol = None
        self.refresh_loop = None
        self.save_state_loop = None

    def stop(self):
        if self.transport is not None:
            self.transport.close()

        if self.refresh_loop:
            self.refresh_loop.cancel()

        if self.save_state_loop:
            self.save_state_loop.cancel()

    def _create_protocol(self):
        return self.protocol_class(self.node, self.storage, self.ksize)

    async def listen(self, port, interface='0.0.0.0', interval=300):
        """
        Start listening on the given port.
        Provide interface="::" to accept ipv6 address
        """
        loop = asyncio.get_event_loop()
        listen = loop.create_datagram_endpoint(self._create_protocol,
                                               local_addr=(interface, port))
        log.info("Node %i listening on %s:%i", self.node.long_id, interface,
                 port)
        self.transport, self.protocol = await listen
        # finally, schedule refreshing table
        self.refresh_table(interval)

    def refresh_table(self, interval=300):
        log.debug("Refreshing routing table")
        asyncio.ensure_future(self._refresh_table(interval))
        loop = asyncio.get_running_loop()
        self.refresh_loop = loop.call_later(interval, self.refresh_table,
                                            interval)

    async def _refresh_table(self, interval=300):
        """
        Refresh buckets that haven't had any lookups in the last hour
        (per section 2.3 of the paper).
        """
        results = []
        for node_id in self.protocol.get_refresh_ids():
            node = Node(node_id)
            nearest = self.protocol.router.find_neighbors(node, self.alpha)
            spider = NodeSpiderCrawl(self.protocol, node, nearest, self.ksize,
                                     self.alpha)
            results.append(spider.find())

        # do our crawling
        await asyncio.gather(*results)

        # now republish keys older than one hour
        for dkey, value in self.storage.iter_older_than(interval):
            await self.set_digest(dkey, value)

    def bootstrappable_neighbors(self):
        """
        Get a :class:`list` of (ip, port) :class:`tuple` pairs suitable for
        use as an argument to the bootstrap method.
        The server should have been bootstrapped
        already - this is just a utility for getting some neighbors and then
        storing them if this server is going down for a while.  When it comes
        back up, the list of nodes can be used to bootstrap.
        """
        neighbors = self.protocol.router.find_neighbors(self.node)
        return [tuple(n)[-2:] for n in neighbors]

    async def bootstrap(self, addrs):
        """
        Bootstrap the server by connecting to other known nodes in the network.
        Args:
            addrs: A `list` of (ip, port) `tuple` pairs.  Note that only IP
                   addresses are acceptable - hostnames will cause an error.
        """
        log.debug("Attempting to bootstrap node with %i initial contacts",
                  len(addrs))
        cos = list(map(self.bootstrap_node, addrs))
        gathered = await asyncio.gather(*cos)
        nodes = [node for node in gathered if node is not None]
        spider = NodeSpiderCrawl(self.protocol, self.node, nodes, self.ksize,
                                 self.alpha)
        return await spider.find()

    async def bootstrap_node(self, addr):
        result = await self.protocol.ping(addr, self.node.id)
        return Node(result[1], addr[0], addr[1]) if result[0] else None

    async def get(self, key):
        """
        Get a key if the network has it.
        Returns:
            :class:`None` if not found, the value otherwise.
        """
        log.info("Looking up key %s", key)
        dkey = digest(key)
        # if this node has it, return it
        if self.storage.get(dkey) is not None:
            return self.storage.get(dkey)
        node = Node(dkey)
        nearest = self.protocol.router.find_neighbors(node)
        if not nearest:
            log.warning("There are no known neighbors to get key %s", key)
            return None
        spider = ValueSpiderCrawl(self.protocol, node, nearest, self.ksize,
                                  self.alpha)
        return await spider.find()

    async def set(self, key, value):
        """
        Set the given string key to the given value in the network.
        """
        if not check_dht_value_type(value):
            raise TypeError(
                "Value must be of type int, float, bool, str, or bytes")
        log.info("setting '%s' = '%s' on network", key, value)
        dkey = digest(key)
        return await self.set_digest(dkey, value)

    async def set_digest(self, dkey, value):
        """
        Set the given SHA1 digest key (bytes) to the given value in the
        network.
        """
        node = Node(dkey)

        nearest = self.protocol.router.find_neighbors(node)
        if not nearest:
            log.warning("There are no known neighbors to set key %s",
                        dkey.hex())
            self.storage[dkey] = value
            return True

        spider = NodeSpiderCrawl(self.protocol, node, nearest, self.ksize,
                                 self.alpha)
        nodes = await spider.find()
        log.info("setting '%s' on %s", dkey.hex(), list(map(str, nodes)))

        # if this node is close too, then store here as well
        biggest = max([n.distance_to(node) for n in nodes])
        if self.node.distance_to(node) < biggest:
            self.storage[dkey] = value
        results = [self.protocol.call_store(n, dkey, value) for n in nodes]
        # return true only if at least one store call succeeded
        return any(await asyncio.gather(*results))

    def save_state(self, fname):
        """
        Save the state of this node (the alpha/ksize/id/immediate neighbors)
        to a cache file with the given fname.
        """
        log.info("Saving state to %s", fname)
        data = {
            'ksize': self.ksize,
            'alpha': self.alpha,
            'id': self.node.id,
            'neighbors': self.bootstrappable_neighbors(),
            'storage': self.storage
        }
        if not data['neighbors']:
            log.warning("No known neighbors, so not writing to cache.")
            # return
        with open(fname, 'wb') as file:
            pickle.dump(data, file)

    @classmethod
    async def load_state(cls, fname, port, interface='0.0.0.0', interval=300):
        """
        Load the state of this node (the alpha/ksize/id/immediate neighbors)
        from a cache file with the given fname and then bootstrap the node
        (using the given port/interface to start listening/bootstrapping).
        """
        log.info("Loading state from %s", fname)
        with open(fname, 'rb') as file:
            data = pickle.load(file)
        svr = cls(data['ksize'], data['alpha'], data['id'], data['storage'])
        await svr.listen(port, interface, interval)
        if data['neighbors']:
            await svr.bootstrap(data['neighbors'])
        return svr

    def save_state_regularly(self, fname, frequency=300):
        """
        Save the state of node with a given regularity to the given
        filename.
        Args:
            fname: File name to save retularly to
            frequency: Frequency in seconds that the state should be saved.
                        By default, 10 minutes.
        """
        self.save_state(fname)
        loop = asyncio.get_running_loop()
        self.save_state_loop = loop.call_later(frequency,
                                               self.save_state_regularly,
                                               fname, frequency)


def check_dht_value_type(value):
    """
    Checks to see if the type of the value is a valid type for
    placing in the dht.
    """
    return isinstance(value, (int, float, bool, str, bytes))
