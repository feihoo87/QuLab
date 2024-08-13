import asyncio
import hashlib
import random
import time
from struct import pack

import pytest

from qulab.sys.net.kad import (ForgetfulStorage, KademliaProtocol, KBucket,
                               Node, NodeHeap, RoutingTable, Server,
                               TableTraverser, digest, shared_prefix)


@pytest.fixture()
def bootstrap_node(event_loop):
    server = Server()
    event_loop.run_until_complete(server.listen(8468))

    try:
        yield ('127.0.0.1', 8468)
    finally:
        server.stop()


# pylint: disable=redefined-outer-name
@pytest.fixture()
def mknode():

    def _mknode(node_id=None, ip_addy=None, port=None, intid=None):
        """
        Make a node.  Created a random id if not specified.
        """
        if intid is not None:
            node_id = pack('>l', intid)
        if not node_id:
            randbits = str(random.getrandbits(255))
            node_id = hashlib.sha1(randbits.encode()).digest()
        return Node(node_id, ip_addy, port)

    return _mknode


# pylint: disable=too-few-public-methods
class FakeProtocol:  # pylint: disable=too-few-public-methods

    def __init__(self, source_id, ksize=20):
        self.router = RoutingTable(self, ksize, Node(source_id))
        self.storage = {}
        self.source_id = source_id


# pylint: disable=too-few-public-methods
class FakeServer:

    def __init__(self, node_id):
        self.id = node_id  # pylint: disable=invalid-name
        self.protocol = FakeProtocol(self.id)
        self.router = self.protocol.router


@pytest.fixture()
def fake_server(mknode):
    return FakeServer(mknode().id)


class TestNode:

    def test_long_id(self):  # pylint: disable=no-self-use
        rid = hashlib.sha1(str(random.getrandbits(255)).encode()).digest()
        node = Node(rid)
        assert node.long_id == int(rid.hex(), 16)

    def test_distance_calculation(self):  # pylint: disable=no-self-use
        ridone = hashlib.sha1(str(random.getrandbits(255)).encode())
        ridtwo = hashlib.sha1(str(random.getrandbits(255)).encode())

        shouldbe = int(ridone.hexdigest(), 16) ^ int(ridtwo.hexdigest(), 16)
        none = Node(ridone.digest())
        ntwo = Node(ridtwo.digest())
        assert none.distance_to(ntwo) == shouldbe


class TestNodeHeap:

    def test_max_size(self, mknode):  # pylint: disable=no-self-use
        node = NodeHeap(mknode(intid=0), 3)
        assert not node

        for digit in range(10):
            node.push(mknode(intid=digit))

        assert len(node) == 3
        assert len(list(node)) == 3

    def test_iteration(self, mknode):  # pylint: disable=no-self-use
        heap = NodeHeap(mknode(intid=0), 5)
        nodes = [mknode(intid=x) for x in range(10)]
        for index, node in enumerate(nodes):
            heap.push(node)
        for index, node in enumerate(heap):
            assert index == node.long_id
            assert index < 5

    def test_remove(self, mknode):  # pylint: disable=no-self-use
        heap = NodeHeap(mknode(intid=0), 5)
        nodes = [mknode(intid=x) for x in range(10)]
        for node in nodes:
            heap.push(node)

        heap.remove([nodes[0].id, nodes[1].id])
        assert len(list(heap)) == 5
        for index, node in enumerate(heap):
            assert index + 2 == node.long_id
            assert index < 5


class TestKBucket:

    def test_split(self, mknode):  # pylint: disable=no-self-use
        bucket = KBucket(0, 10, 5)
        bucket.add_node(mknode(intid=5))
        bucket.add_node(mknode(intid=6))
        one, two = bucket.split()
        assert len(one) == 1
        assert one.range == (0, 5)
        assert len(two) == 1
        assert two.range == (6, 10)

    def test_split_no_overlap(self):  # pylint: disable=no-self-use
        left, right = KBucket(0, 2**160, 20).split()
        assert (right.range[0] - left.range[1]) == 1

    def test_add_node(self, mknode):  # pylint: disable=no-self-use
        # when full, return false
        bucket = KBucket(0, 10, 2)
        assert bucket.add_node(mknode()) is True
        assert bucket.add_node(mknode()) is True
        assert bucket.add_node(mknode()) is False
        assert len(bucket) == 2

        # make sure when a node is double added it's put at the end
        bucket = KBucket(0, 10, 3)
        nodes = [mknode(), mknode(), mknode()]
        for node in nodes:
            bucket.add_node(node)
        for index, node in enumerate(bucket.get_nodes()):
            assert node == nodes[index]

    def test_remove_node(self, mknode):  # pylint: disable=no-self-use
        k = 3
        bucket = KBucket(0, 10, k)
        nodes = [mknode() for _ in range(10)]
        for node in nodes:
            bucket.add_node(node)

        replacement_nodes = bucket.replacement_nodes
        assert list(bucket.nodes.values()) == nodes[:k]
        assert list(replacement_nodes.values()) == nodes[k:]

        bucket.remove_node(nodes.pop())
        assert list(bucket.nodes.values()) == nodes[:k]
        assert list(replacement_nodes.values()) == nodes[k:]

        bucket.remove_node(nodes.pop(0))
        assert list(bucket.nodes.values()) == nodes[:k - 1] + nodes[-1:]
        assert list(replacement_nodes.values()) == nodes[k - 1:-1]

        random.shuffle(nodes)
        for node in nodes:
            bucket.remove_node(node)
        assert not bucket
        assert not replacement_nodes

    def test_in_range(self, mknode):  # pylint: disable=no-self-use
        bucket = KBucket(0, 10, 10)
        assert bucket.has_in_range(mknode(intid=5)) is True
        assert bucket.has_in_range(mknode(intid=11)) is False
        assert bucket.has_in_range(mknode(intid=10)) is True
        assert bucket.has_in_range(mknode(intid=0)) is True

    def test_replacement_factor(self, mknode):  # pylint: disable=no-self-use
        k = 3
        factor = 2
        bucket = KBucket(0, 10, k, replacementNodeFactor=factor)
        nodes = [mknode() for _ in range(10)]
        for node in nodes:
            bucket.add_node(node)

        replacement_nodes = bucket.replacement_nodes
        assert len(list(replacement_nodes.values())) == k * factor
        assert list(replacement_nodes.values()) == nodes[k + 1:]
        assert nodes[k] not in list(replacement_nodes.values())


# pylint: disable=too-few-public-methods
class TestRoutingTable:
    # pylint: disable=no-self-use
    def test_add_contact(self, fake_server, mknode):
        fake_server.router.add_contact(mknode())
        assert len(fake_server.router.buckets) == 1
        assert len(fake_server.router.buckets[0].nodes) == 1


# pylint: disable=too-few-public-methods
class TestTableTraverser:
    # pylint: disable=no-self-use
    def test_iteration(self, fake_server, mknode):
        """
        Make 10 nodes, 5 buckets, two nodes add to one bucket in order,
        All buckets: [node0, node1], [node2, node3], [node4, node5],
                     [node6, node7], [node8, node9]
        Test traver result starting from node4.
        """

        nodes = [mknode(intid=x) for x in range(10)]

        buckets = []
        for i in range(5):
            bucket = KBucket(2 * i, 2 * i + 1, 2)
            bucket.add_node(nodes[2 * i])
            bucket.add_node(nodes[2 * i + 1])
            buckets.append(bucket)

        # replace router's bucket with our test buckets
        fake_server.router.buckets = buckets

        # expected nodes order
        expected_nodes = [
            nodes[5], nodes[4], nodes[3], nodes[2], nodes[7], nodes[6],
            nodes[1], nodes[0], nodes[9], nodes[8]
        ]

        start_node = nodes[4]
        table_traverser = TableTraverser(fake_server.router, start_node)
        for index, node in enumerate(table_traverser):
            assert node == expected_nodes[index]


class TestForgetfulStorage:

    def test_storing(self):  # pylint: disable=no-self-use
        storage = ForgetfulStorage(10)
        storage['one'] = 'two'
        assert storage['one'] == 'two'

    def test_forgetting(self):  # pylint: disable=no-self-use
        storage = ForgetfulStorage(0)
        storage['one'] = 'two'
        time.sleep(0.1)
        assert storage.get('one') is None

    def test_iter(self):  # pylint: disable=no-self-use
        storage = ForgetfulStorage(10)
        storage['one'] = 'two'
        for key, value in storage:
            assert key == 'one'
            assert value == 'two'

    def test_iter_old(self):  # pylint: disable=no-self-use
        storage = ForgetfulStorage(10)
        storage['one'] = 'two'
        for key, value in storage.iter_older_than(0):
            assert key == 'one'
            assert value == 'two'


@pytest.mark.asyncio
async def test_storing(bootstrap_node):
    server = Server()
    await server.listen(bootstrap_node[1] + 1)
    await server.bootstrap([bootstrap_node])
    await server.set('key', 'value')
    result = await server.get('key')

    assert result == 'value'

    server.stop()


class TestSwappableProtocol:

    def test_default_protocol(self, event_loop):  # pylint: disable=no-self-use
        """
        An ordinary Server object will initially not have a protocol, but will
        have a KademliaProtocol object as its protocol after its listen()
        method is called.
        """
        server = Server()
        assert server.protocol is None
        event_loop.run_until_complete(server.listen(8469))
        assert isinstance(server.protocol, KademliaProtocol)
        server.stop()

    def test_custom_protocol(self, event_loop):  # pylint: disable=no-self-use
        """
        A subclass of Server which overrides the protocol_class attribute will
        have an instance of that class as its protocol after its listen()
        method is called.
        """

        # Make a custom Protocol and Server to go with hit.
        class CoconutProtocol(KademliaProtocol):
            pass

        class HuskServer(Server):
            protocol_class = CoconutProtocol

        # An ordinary server does NOT have a CoconutProtocol as its protocol...
        server = Server()
        event_loop.run_until_complete(server.listen(8467))
        assert not isinstance(server.protocol, CoconutProtocol)
        server.stop()

        # ...but our custom server does.
        husk_server = HuskServer()
        event_loop.run_until_complete(husk_server.listen(8467))
        assert isinstance(husk_server.protocol, CoconutProtocol)
        husk_server.stop()


class TestUtils:

    def test_digest(self):  # pylint: disable=no-self-use
        dig = hashlib.sha1(b'1').digest()
        assert dig == digest(1)

        dig = hashlib.sha1(b'another').digest()
        assert dig == digest('another')

    def test_shared_prefix(self):  # pylint: disable=no-self-use
        args = ['prefix', 'prefixasdf', 'prefix', 'prefixxxx']
        assert shared_prefix(args) == 'prefix'

        args = ['p', 'prefixasdf', 'prefix', 'prefixxxx']
        assert shared_prefix(args) == 'p'

        args = ['one', 'two']
        assert shared_prefix(args) == ''

        args = ['hi']
        assert shared_prefix(args) == 'hi'
