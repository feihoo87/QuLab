import operator
import typing
from functools import lru_cache, reduce
from itertools import chain, combinations, count, product, repeat

import numpy as np
from scipy.optimize import leastsq
from scipy.sparse import coo_matrix

_default_gates = {
    'I': np.array([[1, 0], [0, 1]]),
    'X': np.array([[1, -1j], [-1j, 1]]) / np.sqrt(2),
    'Y': np.array([[1, 1], [-1, 1]]) / np.sqrt(2)
}


def transformList(n, basic_gates=_default_gates):
    """Tomography 对应的全部变换
    """
    return product(basic_gates.keys(), repeat=n)


def transformMatrix(transform, basic_gates=_default_gates):
    """transform 所对应变换矩阵
    """
    return reduce(np.kron, (basic_gates[k] for k in transform))


@lru_cache()
def transformMatrixElement(transform, r, c, basic_gates=_default_gates):
    """transform 所对应变换矩阵的第 r 行、第 c 列元素
    """
    N = len(transform)
    return reduce(
        operator.mul,
        (basic_gates[k][int(x), int(y)]
         for k, x, y in zip(transform, f'{r:b}'.zfill(N), f'{c:b}'.zfill(N))))


def xFactor(i, transform, j, k):
    """经过 transform 变换后的密度矩阵第 i 个对角元表达式中 x_jk 的系数
    """
    return 2 * np.real(
        np.conj(transformMatrixElement(transform, i, k)) *
        transformMatrixElement(transform, i, j))


def yFactor(i, transform, j, k):
    """经过 transform 变换后的密度矩阵第 i 个对角元表达式中 y_jk 的系数
    """
    return -2 * np.imag(
        np.conj(transformMatrixElement(transform, i, k)) *
        transformMatrixElement(transform, i, j))


def zFactor(i, transform, j):
    """经过 transform 变换后的密度矩阵第 i 个对角元表达式中 z_j 的系数
    """
    return np.real(
        np.conj(transformMatrixElement(transform, i, j)) *
        transformMatrixElement(transform, i, j) -
        np.conj(transformMatrixElement(transform, i, 0)) *
        transformMatrixElement(transform, i, 0))


def constFactor(i, transform):
    """经过 transform 变换后的密度矩阵第 i 个对角元表达式中的常数项
    """
    return np.real(
        np.conj(transformMatrixElement(transform, i, 0)) *
        transformMatrixElement(transform, i, 0))


def rhoToV(rho):
    """密度矩阵转相干矢
    """
    dim = rho.shape[0]
    x = (np.real(rho[i, j]) for i, j in combinations(range(dim), 2))
    y = (np.imag(rho[i, j]) for i, j in combinations(range(dim), 2))
    z = (np.real(rho[i, i]) for i in range(1, dim))
    return np.asarray(list(chain(x, y, z)))


def vToRho(V):
    """相干矢转密度矩阵"""
    dim = int(np.sqrt(len(V) + 1))
    assert dim**2 - 1 == len(V)

    X = V[:(dim**2 - dim) // 2]
    Y = V[(dim**2 - dim) // 2:(dim**2 - dim)]
    Z = V[(dim**2 - dim):]
    rho = np.diag([1 - np.sum(Z)] + list(Z)).astype(np.complex)

    # index [(0, 1), (0, 2), (0, 3), ... (1, 2), (1, 3), ... (2, 3) ...]
    for x, y, (r, c) in zip(X, Y, combinations(range(dim), 2)):
        rho[r, c] = x + 1j * y
        rho[c, r] = x - 1j * y
    return rho


def formUMatrix(n):
    """构造从相干矢到测量结果的转移矩阵"""
    dim = 2**n
    A_data, A_i, A_j = [], [], []
    C = []

    row_counter = count()

    for transform in transformList(n):
        for i in range(1, dim):
            row = next(row_counter)
            C.append(constFactor(i, transform))
            for col, (jk, func) in zip(
                    count(),
                    chain(zip(combinations(range(dim), 2), repeat(xFactor)),
                          zip(combinations(range(dim), 2), repeat(yFactor)),
                          zip(combinations(range(1, dim), 1),
                              repeat(zFactor)))):
                A = func(i, transform, *jk)

                if np.abs(A) > 1e-9:
                    A_i.append(row)
                    A_j.append(col)
                    A_data.append(A)
    return coo_matrix((A_data, (A_i, A_j))), np.asarray(C)


def acquireVFromData(n, P):
    """从测量数据中还原相干矢
    """

    def error(v, A, C, P):
        return np.asarray((A @ v + C - P))

    p0 = np.zeros(2**(2 * n) - 1)
    A, C = formUMatrix(n)
    v, _ = leastsq(error, p0, args=(A, C, P))
    return v
