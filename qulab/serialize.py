import inspect
import lzma
import pickle
import struct
from typing import Any, Callable, TypeVar

import numpy as np
from qulab import umsgpack

__index = 0
__pack_handlers = {}
__unpack_handlers = {}

cls = TypeVar('cls')


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
    __pack_handlers[cls] = lambda obj: umsgpack.Ext(t, encode(obj))
    __unpack_handlers[t] = lambda ext: decode(ext.data)


def pack(obj: Any) -> bytes:
    """
    Serialize
    """
    return umsgpack.packb(obj, ext_handlers=__pack_handlers)


def unpack(buff: bytes) -> Any:
    """
    Unserialize
    """
    return umsgpack.unpackb(buff, ext_handlers=__unpack_handlers)


def packz(obj: Any) -> bytes:
    """
    Serialize and compress.
    """
    return lzma.compress(pack(obj), format=lzma.FORMAT_XZ)


def unpackz(buff: bytes) -> Any:
    """
    Decompress and unserialize.
    """
    return unpack(lzma.decompress(buff, format=lzma.FORMAT_XZ))


register(np.ndarray)


def parse_frame(frame):
    ret = {}
    ret['source'] = inspect.getsource(frame)
    ret['name'] = frame.f_code.co_name
    if ret['name'] != '<module>':
        argnames = frame.f_code.co_varnames[:frame.f_code.co_argcount +
                                            frame.f_code.co_kwonlyargcount]
        ret['name'] += '(' + ', '.join(argnames) + ')'
        ret['firstlineno'] = frame.f_code.co_firstlineno
    else:
        ret['firstlineno'] = 1
    ret['filename'] = frame.f_code.co_filename
    return ret


def parse_traceback(err):
    ret = []
    tb = err.__traceback__
    while tb is not None:
        frame = parse_frame(tb.tb_frame)
        frame['lineno'] = tb.tb_lineno
        ret.append(frame)
        tb = tb.tb_next
    return ret


def format_traceback(err):
    lines = []
    for frame in parse_traceback(err):
        lines.append(f"{frame['filename']} in {frame['name']}")
        for n, line in enumerate(frame['source'].split('\n')):
            lno = n + frame['firstlineno']
            lines.append(
                f"{'->' if lno==frame['lineno'] else '  '}{lno:3d} {line}")
    traceback_text = '\n'.join(lines)
    args = list(err.args)
    args.append(traceback_text)
    err.args = tuple(args)
    return err


def encode_excepion(e: Exception) -> bytes:
    e = format_traceback(e)
    e.__traceback__ = None
    return pickle.dumps(e)


register(Exception, encode_excepion)
