import struct

import numpy as np

types = {
    "b"      : (  int, 'b'), "B"      : (  int, 'B'),
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
    if isinstance(datalist, bytes):
        datablock = datalist
    else:
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

    return header.encode() + datablock


def decode_IEEE_488_2_BinBlock(data, dtype="int16", is_big_endian=True):
    """
    解析 IEEE 488.2 标准二进制块

    Args:
        data : 二进制块
        dtype : 数据类型
        endian : 字节序

    Returns:
        datalist
    """
    if isinstance(data, bytes):
        header = data[:2]
        size = int(data[2:2 + int(header[1:2])])
        assert size == len(data) - 2 - int(header[1:2]), "data size error"
        datablock = data[2 + int(header[1:2]):size + 2 + int(header[1:2])]
    else:
        raise ValueError("data must be bytes")

    if is_big_endian:
        endianc = '>'
    else:
        endianc = '<'
    datalist = list(
        struct.unpack(
            '%s%d%s' % (endianc, size // struct.calcsize(types[dtype][1]),
                        types[dtype][1]), datablock))

    return datalist
