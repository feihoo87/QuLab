# -*- coding: utf-8 -*-
import functools
import os
import socket
import struct
import uuid
from hashlib import sha1

import numpy as np


def IEEE_488_2_BinBlock(datalist, dtype="int16", is_big_endian=True):
    """
    将一组数据打包成 IEEE 488.2 标准二进制块

    Args:
        datalist : 要打包的数字列表
        dtype    : 数据类型
        endian   : 字节序

    Returns:
        binblock, header
        二进制块, 以及其 'header'
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
             "float32": (float, 'f'), "float64": (float, 'd')
    } # yapf: disable

    datalist = np.asarray(datalist)
    datalist.astype(types[dtype][0])
    if is_big_endian:
        endianc = '>'
    else:
        endianc = '<'
    datablock = struct.pack(
        '%s%d%s' % (endianc, len(datalist), types[dtype][1]), *datalist)
    size = '%d' % len(datablock)
    header = '#%d%s' % (len(size), size)

    return header.encode() + datablock, header


@functools.lru_cache(maxsize=1)
def getHostIP():
    """
    获取本机 ip 地址
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip


@functools.lru_cache(maxsize=1)
def getHostIPv6():
    """
    获取本机 ipv6 地址
    """
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        s.connect(('2001:4860:4860::8888', 80, 0, 0))
        ip = s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()
    return ip


@functools.lru_cache(maxsize=1)
def getHostMac():
    """
    获取本机 mac 地址
    """
    mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
    return ":".join([mac[e:e + 2] for e in range(0, 11, 2)])


def randomID():
    """
    Generate a random msg ID.
    """
    msgID = sha1(os.urandom(32)).digest()
    return msgID
