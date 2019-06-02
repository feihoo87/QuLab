import pytest
from qulab.dht.network import Server


@pytest.fixture
def bootstrap_nodes(event_loop):
    servers = [Server() for i in range(3)]
    for server in servers:
        event_loop.run_until_complete(server.start())

    try:
        yield [('127.0.0.1', server.port) for server in servers]
    finally:
        for server in servers:
            server.stop()
