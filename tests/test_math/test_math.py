import numpy as np

from qulab.math import *


def test_math():
    assert get_unit_prefix(1.23e5) == ('k', 1000.0)
    assert np.abs(skew(np.random.randn(1000))) < 1
    assert np.abs(kurtosis(np.random.randn(1000))) < 1
    P, E, std, (low, high) = get_probility(500, 1000)
    assert P == 0.5
    state0 = np.random.randn(1000) - 1
    state1 = np.random.randn(1000) + 1
    assert np.abs(threshold(np.array(list(state0) + list(state1)))) < 1
    thr, vis, (a, b) = get_threshold_visibility(state0, state1)
    assert abs(thr) < 1
    assert 0 < vis < 1
    assert FWHM_of_normal_distribution(Std_of_norm_from_FWHM(1)) == 1


def test_vonNeumannEntropy():
    N = 10
    v = np.random.rand(1, N) + np.random.rand(1, N) * 1j
    rho = np.conj(v).T.dot(v) / np.conj(v).dot(v.T)
    S = vonNeumannEntropy(rho)
    assert abs(S) < 1e-12
    v = np.random.rand(1, N) + np.random.rand(1, N) * 1j
    rho = 0.5 * rho + 0.5 * np.conj(v).T.dot(v) / np.conj(v).dot(v.T)
    assert vonNeumannEntropy(rho) > S
