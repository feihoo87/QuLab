import typing
from functools import reduce
from itertools import product

import numpy as np


def splite_at(l, bits):
    """将 l 的二进制位于 bits 所列的位置上断开插上0
    
    如 splite_at(int('1111',2), [0,2,4,6]) == int('10101010', 2)
    bits 必须从小到大排列
    """
    r = l
    for n in bits:
        mask = (1 << n) - 1
        low = r & mask
        high = r - low
        r = (high << 1) + low
    return r


def place_at(l, bits):
    """将 l 的二进制位置于 bits 所列的位置上
    
    如 place_at(int('10111',2), [0,2,4,5,6]) == int('01010101', 2)
    """
    r = 0
    for index, n in enumerate(bits):
        b = (l >> index) & 1
        r += b << n
    return r


def subspace(i, j, sub_index):
    r, c = splite_at(i, sub_index), splite_at(j, sub_index)
    for l in range(2**len(sub_index)):
        n = place_at(l, sub_index)
        yield r | n, c | n


def ptrace(rho, N, sub_index):
    sub_index = np.atleast_1d(sub_index)
    if len(sub_index) == 1:
        return ptrace_single(rho, N, sub_index[0])
    dim = 2**(N - len(sub_index))
    ret = np.zeros((dim, dim), dtype=np.complex)

    for i, j in product(range(dim), repeat=2):
        for r, c in subspace(i, j, sub_index):
            ret[i, j] += rho[r, c]
    return ret


def ptrace_single(rho, N, k):
    ret = np.zeros((2**(N - 1), 2**(N - 1)), dtype=np.complex)
    step = 2**k
    if N - k + 1 <= k:
        for i, j in product(range(2**(N - k + 1)), repeat=2):
            A = (rho[2 * i * step:(2 * i + 1) * step, 2 * j *
                     step:(2 * j + 1) * step] +
                 rho[(2 * i + 1) * step:(2 * i + 2) * step, (2 * j + 1) *
                     step:(2 * j + 2) * step])
            ret[i * step:(i + 1) * step, j * step:(j + 1) * step] = A
    else:
        for i, j in product(range(2**(k)), repeat=2):
            B1 = rho[i + step::2 * step, j + step::2 * step]
            B2 = rho[i::2 * step, j::2 * step][:B1.shape[0], :B1.shape[1]]
            A = B2 + B1
            ret[i:i + step * A.shape[0]:step, j:j + step * A.shape[1]:step] = A
    return ret


def trace(rho, sub_mask=None):
    """对密度矩阵求迹
    
    当给定 sub_mask 时，对指定对子系统求迹
    """
    N = int(np.log2(rho.shape[0]))
    if isinstance(sub_mask, str):
        sub_mask = int(sub_mask, 2)
    elif isinstance(sub_mask, int):
        pass
    elif isinstance(sub_mask, typing.Iterable):
        sub_mask = reduce(lambda a, b: (a << 1) + b, sub_mask)

    if sub_mask is None or sub_mask == (1 << N) - 1:
        return np.trace(rho)
    else:
        while sub_mask & (1 << (N - 1)):
            rho = rho[:2**(N - 1), :2**(N - 1)] + rho[2**(N - 1):, 2**(N - 1):]
            sub_mask &= (1 << (N - 1)) - 1
            N -= 1
        while sub_mask & 1:
            rho = rho[::2, ::2] + rho[1::2, 1::2]
            sub_mask >>= 1
            N -= 1
        if sub_mask == 0:
            return rho
        sub_index = [i for i in range(N) if ((sub_mask >> i) & 1)]
        return ptrace(rho, N, sub_index)
