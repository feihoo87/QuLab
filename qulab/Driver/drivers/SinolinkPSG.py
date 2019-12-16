import logging
import socket
from contextlib import contextmanager

import numpy as np

from qulab.Driver import BaseDriver, QReal, QInteger, QString, QOption, QBool, QVector, QList

log = logging.getLogger('qulab.Driver')


class Driver(BaseDriver):

    support_models = []

    quants = [
        QReal('Frequency',
              unit='Hz',
              set_cmd='FREQ %(value).9e Hz',
              get_cmd='FREQ?'),
        QReal('Power',
              unit='dBm',
              set_cmd='LEVEL %(value).5e dBm',
              get_cmd='LEVEL?'),
        QOption('Output',
                set_cmd='LEVEL:STATE %(option)s',
                options=[('OFF', 'OFF'), ('ON', 'ON')]),
    ]

    CHs=[1]

    def __init__(self, addr, **kw):
        super().__init__(addr, **kw)
        self.port = kw.get('port', 2000)

    @contextmanager
    def _socket(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.addr, self.port))
            yield s

    def write(self, cmd):
        if isinstance(cmd, str):
            cmd = cmd.encode()
        with self._socket() as s:
            s.send(cmd)
            log.debug(f"{self.addr}:{self.port} << {cmd}")

    def query(self, cmd):
        if isinstance(cmd, str):
            cmd = cmd.encode()
        with self._socket() as s:
            s.send(cmd)
            log.debug(f"{self.addr}:{self.port} << {cmd}")
            ret = s.recv(1024).decode()
            log.debug(f"{self.addr}:{self.port} >> {ret}")
            return ret

    # @property
    # def freq(self):
    #     return float(self.query('FREQ?'))

    # @freq.setter
    # def freq(self, f):
    #     self.write(f'FREQ {f} Hz')

    # @property
    # def power(self):
    #     return float(self.query('LEVEL?'))

    # @power.setter
    # def power(self, p):
    #     self.write(f'LEVEL {p} dBm')

    # def setValue(self, name, value, **kw):
    #     if name == 'Power':
    #         self.power = value
    #     elif name == 'Frequency':
    #         self.freq = value
    #     elif name == 'Output':
    #         self.write(f'LEVEL:STATE {value}')
