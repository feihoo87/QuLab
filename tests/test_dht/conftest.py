import pytest

from qulab.dht.network import Server


@pytest.yield_fixture
def bootstrap_node(event_loop):
    server = Server()
    port = event_loop.run_until_complete(server.listen_on_random_port())

    try:
        yield ('127.0.0.1', port)
    finally:
        server.stop()