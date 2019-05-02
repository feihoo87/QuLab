import pickle
import struct
from typing import Any

import umsgpack


def pack(obj: Any) -> bytes:
    return umsgpack.packb(obj)


def unpack(buff: bytes) -> Any:
    return umsgpack.unpackb(buff)
