from qulab.math.qst import *
import numpy as np


def randomRho(n):
    v = np.random.rand(1, 2**n) + np.random.rand(1, 2**n) * 1j - 0.5 - 0.5j
    return np.conj(v).T.dot(v) / np.conj(v).dot(v.T)


def aquireData(rho, transform):
    mat = transformMatrix(transform)
    ret = mat.dot(rho.dot(np.conj(mat.T)))
    ret = np.real(np.diag(ret))
    return ret[1:]


def test_qst():
    n = 4

    rho = randomRho(n)
    V = rhoToV(rho)
    P = []

    for index, transform in enumerate(transformList(n)):
        z = aquireData(rho, transform)
        P.extend(list(z))

    v = acquireVFromData(n, P)

    assert np.sum((v - V)**2) < 1e-12
    assert np.max(np.abs(rho - vToRho(v))) < 1e-6
