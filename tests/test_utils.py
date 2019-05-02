from qulab.utils import *
import numpy as np
def test_utils():
    assert get_unit_prefix(1.23e5) == ('k', 1000.0)
    assert np.abs(skew(np.random.randn(1000))) < 1
    assert np.abs(kurtosis(np.random.randn(1000))) < 1
    P, E, std, (low, high) = get_probility(500, 1000)
    assert P == 0.5
    state0 = np.random.randn(1000) - 1
    state1 = np.random.randn(1000) + 1
    assert np.abs(threshold(np.array(list(state0)+list(state1)))) < 1
    thr, vis, (a, b) = get_threshold_visibility(state0, state1)
    assert abs(thr) < 1
    assert 0 < vis < 1
    buff, header = IEEE_488_2_BinBlock([1,2,3,4,5])
    assert isinstance(buff, bytes)
    assert isinstance(getHostIP(), str)
    assert getHostIPv6() is None or isinstance(getHostIPv6)
    assert isinstance(getHostMac(), str)