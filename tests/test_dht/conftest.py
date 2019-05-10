import logging

import pytest
from qulab.dht.network import Server

log = logging.getLogger()
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())


@pytest.fixture
def bootstrap_node(event_loop):
    server = Server()
    event_loop.run_until_complete(server.start())

    try:
        yield ('127.0.0.1', server.port)
    finally:
        server.stop()
