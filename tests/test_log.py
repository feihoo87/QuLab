import logging
import time

import pytest
import zmq
from qulab.log import *
from qulab.serialize import unpack


def test_level():
    assert level() in [
        logging.NOTSET, logging.DEBUG, logging.INFO, logging.WARNING,
        logging.ERROR, logging.CRITICAL
    ]


def test_BaseHandler():
    hdlr = BaseHandler()
    record = logging.makeLogRecord(dict(name='test', lno=20, msg='hello'))
    bmsg = hdlr.serialize(record)
    assert isinstance(bmsg, bytes)
    record2 = logging.makeLogRecord(unpack(bmsg))
    assert record2.name == hdlr.host + '.' + record.name
    assert record2.msg == record.msg
    with pytest.raises(NotImplementedError):
        hdlr.send_bytes(b'')


def test_logger():
    ctx = zmq.Context()
    interface = "tcp://127.0.0.1"
    with ctx.socket(zmq.PUB) as pub, ctx.socket(zmq.SUB) as sub:
        sub.setsockopt(zmq.LINGER, 0)
        pub.setsockopt(zmq.LINGER, 0)

        port = pub.bind_to_random_port(interface)
        sub.connect('%s:%s' % (interface, port))

        sub.subscribe(b'')
        time.sleep(0.1)

        logger = logging.getLogger('qulabtest')
        logger.setLevel(logging.DEBUG)
        handler = ZMQHandler(pub)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        logger.debug('hello')
        if sub.poll(100):
            btopic, bmsg = sub.recv_multipart()
            record = logging.makeLogRecord(unpack(bmsg))
            assert record.msg == 'hello'
        else:
            assert False, "ZMQ time out."
