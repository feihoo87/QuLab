import numpy as np

from qulab.protocol import *


def test_transport():
    t = Transport()
    d1 = [0, (1, 2), np.array([4, 5, 6])]
    d2 = t.decode(t.encode(d1))
    assert d1[0] == d2[0]
    assert d1[1] == d2[1]
    assert np.all(d1[2] == d2[2])
