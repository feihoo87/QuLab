import pickle

import numpy as np
from qulab.serialize import *


def test_serialize():
    buff = pack((123, 456))
    assert isinstance(buff, bytes)
    assert unpack(buff) == [123, 456]
    x = np.linspace(0, 1, 101)
    buff = pack(x)
    assert isinstance(buff, bytes)
    assert np.all(x == unpack(buff))


class A:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y


def test_register():
    register(A, pickle.dumps, pickle.loads)
    assert A(3, 5) == unpack(pack(A(3, 5)))


def test_compress():
    x = np.zeros(1000)
    buff = pack(x)
    cbuff = packz(x)
    assert len(buff) > len(cbuff)
    assert np.all(x == unpackz(cbuff))
