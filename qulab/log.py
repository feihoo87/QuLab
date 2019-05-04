import logging

import zmq
from qulab._config import config
from qulab.serialize import pack
from qulab.utils import getHostIP

cfg = config.get('log', dict())


class Handler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.ctx = zmq.Context.instance()
        self.socket = self.ctx.socket(zmq.PUB)
        self.logserver = cfg.get('server', None)
        if self.logserver is not None:
            self.socket.connect(self.logserver)
        self.host = getHostIP()

    def __del__(self):
        self.socket.close()

    def emit(self, record):
        """Emit a log message."""
        if self.logserver is None:
            return
        try:
            bmsg = self.serialize(record)
        except Exception:
            self.handleError(record)
            return
        self.socket.send_multipart([bmsg])

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
