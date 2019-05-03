import pickle
import struct
from typing import Any, Callable, TypeVar

import numpy as np
import umsgpack

__index = 0
__pack_handlers = {}
__unpack_handlers = {}

T = TypeVar('T')


def register(cls: type, encode: Callable[[T], bytes],
             decode: Callable[[bytes], T]) -> None:
    global __index
    __index += 1
    t = __index
    __pack_handlers[cls] = lambda obj: umsgpack.Ext(t, encode(obj))
    __unpack_handlers[t] = lambda ext: decode(ext.data)


def pack(obj: Any) -> bytes:
    return umsgpack.packb(obj, ext_handlers=__pack_handlers)


def unpack(buff: bytes) -> Any:
    return umsgpack.unpackb(buff, ext_handlers=__unpack_handlers)


register(np.ndarray, lambda x: x.tobytes(), np.frombuffer)
