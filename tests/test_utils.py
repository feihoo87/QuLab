import numpy as np
from qulab.utils import *


def test_utils():
    buff, header = IEEE_488_2_BinBlock([1, 2, 3, 4, 5])
    assert isinstance(buff, bytes)
    assert isinstance(getHostIP(), str)
    assert isinstance(getHostIPv6(), str)
    assert isinstance(getHostMac(), str)


def test_randomID():
    msgID = randomID()
    assert isinstance(msgID, bytes)
    assert len(msgID) == 20


def test_acceptArg():
    def f1():
        pass

    assert not acceptArg(f1, 'x')

    def f2(x):
        pass

    assert acceptArg(f2, 'x')

    def f3(*args):
        pass

    assert not acceptArg(f3, 'x')
    assert acceptArg(f3, 'x', keyword=False)

    def f4(*x):
        pass

    assert not acceptArg(f4, 'x')

    def f5(**kw):
        pass

    assert acceptArg(f5, 'x')


def test_retry():
    n = 0

    @retry(Exception)
    def f():
        nonlocal n
        n += 1
        if n < 2:
            raise Exception('try more times')
        return 1
    
    assert f() == 1
