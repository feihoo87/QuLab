import logging
import socket
from contextlib import contextmanager

import numpy as np

from qulab import BaseDriver, QList, QOption, QReal

log = logging.getLogger('qulab.driver.SinolinkPSG')


class Driver(BaseDriver):
    def __init__(self, **kw):
        super().__init__(**kw)
        ip = kw.get('addr')
        self.ip = ip
        self.port = kw.get('port', 2000)

    @contextmanager
    def _socket(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.ip, self.port))
            yield s

    def write(self, cmd):
        if isinstance(cmd, str):
            cmd = cmd.encode()
        with self._socket() as s:
            s.send(cmd)
            log.debug(f"{self.ip}:{self.port} << {cmd}")

    def query(self, cmd):
        if isinstance(cmd, str):
            cmd = cmd.encode()
        with self._socket() as s:
            s.send(cmd)
            log.debug(f"{self.ip}:{self.port} << {cmd}")
            ret = s.recv(1024).decode()
            log.debug(f"{self.ip}:{self.port} >> {ret}")
            return ret

    @property
    def freq(self):
        return float(self.query('FREQ?'))

    @freq.setter
    def freq(self, f):
        self.write(f'FREQ {f} Hz')

    @property
    def power(self):
        return float(self.query('LEVEL?'))

    @power.setter
    def power(self, p):
        self.write(f'LEVEL {p} dBm')

    def setValue(self, name, value, **kw):
        if name == 'Power':
            self.power = value
        elif name == 'Frequency':
            self.freq = value
        elif name == 'Output':
            self.write(f'LEVEL:STATE {value}')
