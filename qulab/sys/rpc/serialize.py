import pickle
import zlib
from typing import Any, Callable, TypeVar

import msgpack

__index = 0
__pack_handlers = {}
__unpack_handlers = {}
__compress_level = zlib.Z_NO_COMPRESSION

cls = TypeVar('cls')


def compress_level(level: int) -> None:
    """
    Set compress level

    Args:
        level: int
            An integer from 0 to 9 controlling the level of compression;
            1 is fastest and produces the least compression, 9 is slowest
            and produces the most. 0 is no compression. The default value
            is 0.
    """
    global __compress_level
    __compress_level = level


def register(cls: type,
             encode: Callable[[cls], bytes] = pickle.dumps,
             decode: Callable[[bytes], cls] = pickle.loads) -> None:
    """
    Register a serializable type

    Args:
        cls: type
        encode: Callable
            translate an object of type `cls` into `bytes`
            default: pickle.dumps
        decode: Callable
            translate `bytes` to an object of type `cls`
            default: pickle.loads
    """
    global __index
    __index += 1
    t = __index
    __pack_handlers[cls] = (t, encode)
    __unpack_handlers[t] = decode


def default(obj: Any) -> msgpack.ExtType:
    for cls, (t, encode) in __pack_handlers.items():
        if isinstance(obj, cls):
            return msgpack.ExtType(t, encode(obj))
    else:
        raise TypeError(f"Unknown type: {obj!r}")


def ext_hook(code: int, data: bytes) -> msgpack.ExtType:
    for c, decode in __unpack_handlers.items():
        if code == c:
            return decode(data)
    else:
        return msgpack.ExtType(code, data)


def pack(obj: Any) -> bytes:
    """
    Serialize
    """
    return msgpack.packb(obj, default=default, use_bin_type=True)


def unpack(buff: bytes) -> Any:
    """
    Unserialize
    """
    return msgpack.unpackb(buff, ext_hook=ext_hook, raw=False)


def packz(obj: Any) -> bytes:
    """
    Serialize and compress.
    """
    return zlib.compress(pack(obj), level=__compress_level)


def unpackz(buff: bytes) -> Any:
    """
    Decompress and unserialize.
    """
    return unpack(zlib.decompress(buff))


def encode_excepion(e: Exception) -> bytes:
    e.__traceback__ = None
    return pickle.dumps(e)


register(Exception, encode_excepion)


try:
    import numpy as np

    dtypes = [
        np.bool_, np.int8, np.int16, np.int32, np.int64, np.uint8, np.uint16,
        np.uint32, np.uint64, np.float16, np.float32, np.float64, np.complex64,
        np.complex128
    ]

    _dtype_map1 = {t: i for i, t in enumerate(dtypes)}
    _dtype_map2 = {i: t for i, t in enumerate(dtypes)}

    def encode_ndarray(x: np.ndarray) -> bytes:
        dtype = x.dtype
        if isinstance(dtype, np.dtype):
            dtype = dtype.type
        if x.flags['F_CONTIGUOUS']:
            x = x.T
            T = True
        else:
            T = False
        return pack((_dtype_map1[dtype], x.shape, T, x.data))

    def decode_ndarray(buff: bytes) -> np.ndarray:
        t, shape, T, buff = unpack(buff)
        x = np.ndarray(shape, dtype=_dtype_map2[t], buffer=buff, order='C')
        if T:
            x = x.T
        return x

    register(np.ndarray, encode_ndarray, decode_ndarray)

except:
    pass

__all__ = ['compress_level', 'register', 'pack', 'unpack', 'packz', 'unpackz']
