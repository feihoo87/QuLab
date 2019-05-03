import numpy as np
from qulab.utils import *


def test_utils():
    buff, header = IEEE_488_2_BinBlock([1, 2, 3, 4, 5])
    assert isinstance(buff, bytes)
    assert isinstance(getHostIP(), str)
    assert getHostIPv6() is None or isinstance(getHostIPv6(), str)
    assert isinstance(getHostMac(), str)
