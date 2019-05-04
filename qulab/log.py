import logging

import zmq
from qulab._config import config
from qulab.serialize import pack, unpack
from qulab.utils import getHostIP

cfg = config.get('log', dict())


def level():
    """
    Get default log level
    """
    return {
        'notset': logging.NOTSET,
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL
    }[cfg.get('level', 'info')] # yapf: disable


class BaseHandler(logging.Handler):
    """
    BaseHandler
    """

    def __init__(self):
        super().__init__()
        self.host = getHostIP()

    def emit(self, record):
        """Emit a log message."""
        try:
            bmsg = self.serialize(record)
        except Exception:
            self.handleError(record)
            return
        self.send_bytes(bmsg)

    def send_bytes(self, bmsg):
        raise NotImplementedError

    def serialize(self, record):
        """
        Serialize the record in binary format, and returns it ready for
        transmission across the socket.
        """
        ei = record.exc_info
        if ei:
            # just to get traceback text into record.exc_text ...
            dummy = self.format(record)
        # See issue #14436: If msg or args are objects, they may not be
        # available on the receiving end. So we convert the msg % args
        # to a string, save it as msg and zap the args.
        d = dict(record.__dict__)
        d['msg'] = record.getMessage()
        d['args'] = None
        d['exc_info'] = None
        # Issue #25685: delete 'message' if present: redundant with 'msg'
        d.pop('message', None)
        if d['name'] == 'root':
            d['name'] = self.host
        else:
            d['name'] = '%s.%s' % (self.host, d['name'])
        s = pack(d)
        return s


class ZMQHandler(BaseHandler):
    """
    Publish log by zmq socket
    """

    def __init__(self, socket: zmq.Socket):
        """
        Args:
            socket: A :class:`~zmq.Socket` instance.
        """
        super().__init__()
        self.socket = socket

    def send_bytes(self, bmsg):
        btopic = self.host.encode()
        self.socket.send_multipart([btopic, bmsg])


class RedisHandler(BaseHandler):
    """
    Publish log by redis
    """

    def __init__(self, conn, channel='log'):
        """
        Args:
            conn : :class:`~redis.Redis`
                redis connection
            channle : str
                channel name
        """
        super().__init__()
        self.conn = conn
        self.channel = channel

    def send_bytes(self, bmsg):
        self.conn.publish(self.channel, bmsg)
