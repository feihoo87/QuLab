import asyncio
import pickle
import unittest

import pytest
from qulab.dht.network import Server, digest
from qulab.dht.protocol import KademliaProtocol


@pytest.mark.asyncio
async def test_save_state(bootstrap_nodes, tmp_path):
    server = Server()
    state_file = tmp_path / 'state.dat'
    port = await server.listen_on_random_port()
    assert port != bootstrap_nodes[0][1]
    await server.bootstrap(bootstrap_nodes)
    assert set(server.bootstrappable_neighbors()) == set(bootstrap_nodes)
    server.save_state_regularly(state_file)
    assert state_file.exists()
    data = pickle.loads(state_file.read_bytes())
    assert data['id'] == server.node.id
    assert set(data['neighbors']) == set(bootstrap_nodes)
    server.stop()

    server = Server.load_state(state_file)
    await asyncio.sleep(0.1)
    assert set(server.bootstrappable_neighbors()) == set(bootstrap_nodes)
    server.stop()
    state_file.unlink()


@pytest.mark.asyncio
async def test_storing(bootstrap_nodes):
    server = Server()
    port = await server.listen_on_random_port()
    await server.bootstrap(bootstrap_nodes)

    await server.set('key', 'value')
    result = await server.get('key')

    assert result == 'value'

    await server.set_digest(digest('hello'), 'world')
    result = await server.get('hello')
    assert result == 'world'
    result = await server.get_digest(digest('hello'))
    assert result == 'world'

    server.stop()

    server = Server()
    port = await server.listen_on_random_port()
    await server.bootstrap(bootstrap_nodes)
    result = await server.get('key')
    assert result == 'value'
    result = await server.get('hello')
    assert result == 'world'
    result = await server.get_digest(digest('hello'))
    assert result == 'world'
    server.stop()


class SwappableProtocolTests(unittest.TestCase):
    def test_default_protocol(self):
        """
        An ordinary Server object will initially not have a protocol, but will
        have a KademliaProtocol object as its protocol after its listen()
        method is called.
        """
        loop = asyncio.get_event_loop()
        server = Server()
        self.assertIsNone(server.protocol)
        loop.run_until_complete(server.listen(8469))
        self.assertIsInstance(server.protocol, KademliaProtocol)
        server.stop()

    def test_custom_protocol(self):
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
        loop = asyncio.get_event_loop()
        server = Server()
        loop.run_until_complete(server.listen(8469))
        self.assertNotIsInstance(server.protocol, CoconutProtocol)
        server.stop()

        # ...but our custom server does.
        husk_server = HuskServer()
        loop.run_until_complete(husk_server.listen(8469))
        self.assertIsInstance(husk_server.protocol, CoconutProtocol)
        husk_server.stop()
