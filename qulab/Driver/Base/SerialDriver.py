import serial # use the pyserial module (https://pypi.python.org/pypi/pyserial)

import logging
import numpy as np

from .BaseDriver import BaseDriver
from .quant import QReal, QInteger, QString, QOption, QBool, QVector, QList, newcfg

log = logging.getLogger('qulab.Driver')

class SerialDriver(BaseDriver):

    error_command = 'SYST:ERR?'
    """The SCPI command to query errors."""

    def __init__(self, addr=None, baudrate=115200, timeout=3, **kw):
        super().__init__(addr, timeout, **kw)
        self._baudrate = baudrate

    def __repr__(self):
        return 'SerialDriver(addr=%s,model=%s)' % (self.addr,self.model)

    def performOpen(self, **kw):
        try:
            if not self.handle.isOpen():
                self.handle.open()
        except:
            self.handle=serial.Serial(self.addr,baudrate=self._baudrate,timeout=self.timeout)
        try:
            IDN = self.query("*IDN?").split(',')
            company = IDN[0].strip()
            model = IDN[1].strip()
            version = IDN[3].strip()
            self.model = model
        except:
            raise IOError('query IDN error!')

    def performClose(self, **kw):
        self.handle.close()

    def performOPC(self):
        opc=int(self.query("*OPC?"))
        return opc

    def set_timeout(self, t):
        self.timeout = t
        if self.handle is not None:
            self.handle.timeout = t

    def errors(self):
        """返回错误列表"""
        e = []
        if self.error_command == '':
            return e
        while True:
            s = self.query(self.error_command)
            _ = s.strip(' \n\r').split(',')
            code = int(_[0])
            msg = _[1]
            if code == 0:
                break
            e.append((code, msg))
        return e
            
    def query(self, message):
        if self.handle is None:
            return None
        log.debug("%s << %s", str(self.handle), message)
        try:
            message_byte=(message+'\n').encode()   #格式化字符串 
            self.handle.write(message_byte)
            res_byte = self.handle.readline()
            # 如果写入的命令失败返回的结果为badCommandResponse = b'[BADCOMMAND]\r\n'  (DAT64H)
            res = res_byte.decode()
        except:
            log.exception("%s << %s", str(self.handle), message)
            raise
        log.debug("%s >> %s", str(self.handle), res)
        return res

    def write(self, message):
        """Send message to the instrument."""
        if self.handle is None:
            return None
        log.debug("%s << %s", str(self.handle), message)
        try:
            message_byte=(message+'\n').encode()  #格式化字符串
            ret = self.handle.write(message_byte)
        except:
            log.exception("%s << %s", str(self.handle), message)
            raise
