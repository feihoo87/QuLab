import numpy as np
from qulab.serialize import *


def test_serialize():
    buff = pack((123, 456))
    assert isinstance(buff, bytes)
    assert unpack(buff) == [123, 456]
