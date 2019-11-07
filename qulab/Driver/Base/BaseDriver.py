# -*- coding: utf-8 -*-
import copy
import logging
import numpy as np
import visa
import struct
from datetime import datetime

from .quant import QReal, QInteger, QString, QOption, QBool, QVector, QList, newcfg

log = logging.getLogger('qulab.Driver')
__all__ = [
    'BaseDriver', 'visaDriver'
]

class BaseDriver(object):

    support_models = []
    """the confirmed models supported by this driver"""

    quants = []

    CHs=[1,2,3,4]
    '''Channels list, default is 4 channels'''

    def __init__(self, addr=None, timeout=3, **kw):
        self.addr = addr
        self.timeout = timeout
        self.handle = kw.get('handle',None)
        self.model = kw.get('model',None)
        self.config = newcfg(self.quants, self.CHs)
        self.quantities={}
        for quant in self.quants:
            self.quantities[quant.name] = copy.deepcopy(quant)

    def __repr__(self):
        return 'Driver(addr=%s,model=%s)' % (self.addr,self.model)

    def __del__(self):
        self.close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.close()

    def newcfg(self):
        self.config = newcfg(self.quants, self.CHs)
        log.info('new config!')

    def getcfg(self):
        return self.config

    def set(self, cfg={}, **kw):
        assert isinstance(cfg,dict)
        cfg.update(**kw)
        for key, value in cfg.items():
            if isinstance(value,dict):
                self.setValue(key, **value)
            else:
                self.setValue(key, value)

    def performOpen(self,**kw):
        pass

    def performClose(self,**kw):
        pass

    def open(self, **kw):
        self.performOpen(**kw)
        log.info(f'{datetime.now()}    Open Instrument {self.model}@{self.addr}')

    def close(self, **kw):
        self.performClose(**kw)
        log.info(f'{datetime.now()}    Close Instrument {self.model}@{self.addr}')

    def performOPC(self):
        return 1

    def performSetValue(self, quant, value, **kw):
        if quant.set_cmd is not '':
            quant.set(self,value,**kw)
        else:
            pass

    def performGetValue(self, quant, **kw):
        if quant.get_cmd is not '':
            return quant.get(self,**kw)
        else:
            return self.config[quant.name][kw['ch']]['value']

    def setValue(self, name, value, **kw):
        assert name in self.quantities
        quant=self.quantities[name]
        _kw=copy.deepcopy(quant.default)
        _kw.update(value=value,**kw)
        self.performSetValue(quant, **_kw)
        log.info('%s    Set Value of CH-%s: %s --> %s %s' % (datetime.now(),_kw.get('ch'),name,value,_kw.get('unit')))
        self.config[name][_kw.pop('ch')].update(_kw) # update config
        opc=self.performOPC()
        return opc

    def getValue(self, name, **kw):
        assert name in self.quantities
        quant=self.quantities[name]
        _kw=copy.deepcopy(quant.default)
        _kw.update(**kw)
        value = self.performGetValue(quant, **_kw)
        _kw.update(value=value)
        log.info('%s    Get Value of CH-%s: %s <-- %s %s' % (datetime.now(),_kw.get('ch'),name,value,_kw.get('unit')))
        self.config[name][_kw.pop('ch')].update(_kw) # update config
        return value

    def query(self,message,**kw):
        return

    def write(self,message,**kw):
        pass


class visaDriver(BaseDriver):

    error_command = 'SYST:ERR?'
    """The SCPI command to query errors."""


    def __init__(self, addr=None, timeout=3, visa_backend='@ni', **kw):
        super(visaDriver, self).__init__(addr, timeout, **kw)
        self.visa_backend='@ni'

    def __repr__(self):
        return 'visaDriver(addr=%s,model=%s)' % (self.addr,self.model)

    def performOpen(self, **kw):
        try:
            self.handle.open()
        except:
            rm = visa.ResourceManager(self.visa_backend)
            self.handle = rm.open_resource(self.addr)
        self.handle.timeout = self.timeout * 1000
        try:
            IDN = self.handle.query("*IDN?").split(',')
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
            self.handle.timeout = t * 1000

    def errors(self):
        """返回错误列表"""
        e = []
        if self.error_command == '':
            return e
        while True:
            s = self.handle.query(self.error_command)
            _ = s[:-1].split(',"')
            code = int(_[0])
            msg = _[1]
            if code == 0:
                break
            e.append((code, msg))
        return e

    def query(self, message, mode=None,):
        if self.handle is None:
            return None
        log.debug("%s << %s", str(self.handle), message)
        try:
            if mode is None:
                res = self.handle.query(message)
            elif mode in ['ascii']:
                res = self.handle.query_ascii_values(message, converter='f',
                        separator=',', container=list, delay=None)
            elif mode in ['binary']:
                res = self.handle.query_binary_values(message, datatype='f',
                        is_big_endian=False, container=list, delay=None,
                        header_fmt='ieee')
        except:
            log.exception("%s << %s", str(self.handle), message)
            raise
        log.debug("%s >> %s", str(self.handle), res)
        return res

    def query_ascii_values(self, message, converter='f', separator=',',
                           container=list, delay=None,):
        if self.handle is None:
            return None
        log.debug("%s << %s", str(self.handle), message)
        try:
            res = self.handle.query_ascii_values(
                message, converter, separator, container, delay)
        except:
            log.exception("%s << %s", str(self.handle), message)
            raise
        log.debug("%s >> <%d results>", str(self.handle), len(res))
        return res

    def query_binary_values(self, message, datatype='f', is_big_endian=False,
                            container=list, delay=None,
                            header_fmt='ieee',):
        if self.handle is None:
            return None
        log.debug("%s << %s", str(self.handle), message)
        try:
            res = self.handle.query_binary_values(message, datatype,
                            is_big_endian,container, delay, header_fmt)
        except:
            log.exception("%s << %s", str(self.handle), message)
            raise
        log.debug("%s >> <%d results>", str(self.handle), len(res))
        return res

    def write(self, message):
        """Send message to the instrument."""
        if self.handle is None:
            return None
        log.debug("%s << %s", str(self.handle), message)
        try:
            ret = self.handle.write(message)
        except:
            log.exception("%s << %s", str(self.handle), message)
            raise

    def write_ascii_values(self, message, values, converter='f', separator=',',
                           termination=None, encoding=None,):
        if self.handle is None:
            return None
        log_msg = message+('<%d values>' % len(values))
        log.debug("%s << %s", str(self.handle), log_msg)
        try:
            ret = self.handle.write_ascii_values(message, values, converter,
                                              separator, termination, encoding)
        except:
            log.exception("%s << %s", str(self.handle), log_msg)
            raise

    def write_binary_values(self, message, values, datatype='f',
                                is_big_endian=False, termination=None,
                                encoding=None,):
        if self.handle is None:
            return None
        block, header = IEEE_488_2_BinBlock(values, datatype, is_big_endian)
        log_msg = message+header+'<DATABLOCK>'
        log.debug("%s << %s", str(self.handle), log_msg)
        try:
            ret = self.handle.write_binary_values(message, values, datatype,
                                    is_big_endian, termination, encoding)
        except:
            log.exception("%s << %s", str(self.handle), log_msg)
            raise


def IEEE_488_2_BinBlock(datalist, dtype="int16", is_big_endian=True):
    """将一组数据打包成 IEEE 488.2 标准二进制块

    datalist : 要打包的数字列表
    dtype    : 数据类型
    endian   : 字节序

    返回二进制块, 以及其 'header'
    """
    types = {"b"      : (  int, 'b'), "B"      : (  int, 'B'),
             "h"      : (  int, 'h'), "H"      : (  int, 'H'),
             "i"      : (  int, 'i'), "I"      : (  int, 'I'),
             "q"      : (  int, 'q'), "Q"      : (  int, 'Q'),
             "f"      : (float, 'f'), "d"      : (float, 'd'),
             "int8"   : (  int, 'b'), "uint8"  : (  int, 'B'),
             "int16"  : (  int, 'h'), "uint16" : (  int, 'H'),
             "int32"  : (  int, 'i'), "uint32" : (  int, 'I'),
             "int64"  : (  int, 'q'), "uint64" : (  int, 'Q'),
             "float"  : (float, 'f'), "double" : (float, 'd'),
             "float32": (float, 'f'), "float64": (float, 'd')}

    datalist = np.asarray(datalist)
    datalist.astype(types[dtype][0])
    if is_big_endian:
        endianc = '>'
    else:
        endianc = '<'
    datablock = struct.pack('%s%d%s' % (endianc, len(datalist), types[dtype][1]), *datalist)
    size = '%d' % len(datablock)
    header = '#%d%s' % (len(size),size)

    return header.encode()+datablock, header
