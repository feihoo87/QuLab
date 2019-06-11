import operator
from functools import reduce
from itertools import chain, compress, product

import numpy as np

from qulab.math.trace import trace


def test_trace():
    N = 5
    mat_lst = [np.random.randint(500, size=(2, 2)) for i in range(N)]
    A = reduce(np.kron, mat_lst)
    
    for sub_mask in product([0, 1], repeat=N):
        res1 = trace(A, sub_mask)
        res2 = reduce(np.kron, compress(
            mat_lst, 1 - np.array(sub_mask)), 1) * reduce(
                operator.mul, map(np.trace, compress(mat_lst, sub_mask)), 1)
        assert np.all(res1 == res2)

    assert np.all(trace(A, '01100') == trace(A, [0, 1, 1, 0, 0]))
    assert np.all(trace(A, '01100') == trace(A, 12))
