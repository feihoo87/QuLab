from functools import reduce

import numpy as np

from qulab.math.trace import trace


def test_trace():
    a4 = np.array([[2, 3], [5, 7]])
    a3 = np.array([[11, 13], [17, 19]])
    a2 = np.array([[23, 29], [31, 37]])
    a1 = np.array([[41, 43], [47, 53]])
    a0 = np.array([[59, 61], [67, 71]])
    A = reduce(np.kron, [a4, a3, a2, a1, a0])

    assert np.all(
        trace(A, '00001') == reduce(np.kron, [a4, a3, a2, a1]) * np.trace(a0))
    assert np.all(
        trace(A, '10000') == reduce(np.kron, [a3, a2, a1, a0]) * np.trace(a4))
    assert np.all(
        trace(A, '01000') == reduce(np.kron, [a4, a2, a1, a0]) * np.trace(a3))
    assert np.all(
        trace(A, '00010') == reduce(np.kron, [a4, a3, a2, a0]) * np.trace(a1))
    assert np.all(
        trace(A, '00100') == reduce(np.kron, [a4, a3, a1, a0]) * np.trace(a2))
    assert np.all(
        trace(A, '00011') == reduce(np.kron, [a4, a3, a2]) * np.trace(a1) *
        np.trace(a0))
    assert np.all(
        trace(A, '00101') == reduce(np.kron, [a4, a3, a1]) * np.trace(a2) *
        np.trace(a0))
    assert np.all(
        trace(A, '01001') == reduce(np.kron, [a4, a2, a1]) * np.trace(a3) *
        np.trace(a0))
    assert np.all(
        trace(A, '10001') == reduce(np.kron, [a3, a2, a1]) * np.trace(a4) *
        np.trace(a0))
    assert np.all(
        trace(A, '00110') == reduce(np.kron, [a4, a3, a0]) * np.trace(a2) *
        np.trace(a1))
    assert np.all(
        trace(A, '01010') == reduce(np.kron, [a4, a2, a0]) * np.trace(a3) *
        np.trace(a1))
    assert np.all(
        trace(A, '10010') == reduce(np.kron, [a3, a2, a0]) * np.trace(a4) *
        np.trace(a1))
    assert np.all(
        trace(A, '00111') == reduce(np.kron, [a4, a3]) * np.trace(a2) *
        np.trace(a1) * np.trace(a0))
    assert np.all(
        trace(A, '01011') == reduce(np.kron, [a4, a2]) * np.trace(a3) *
        np.trace(a1) * np.trace(a0))
    assert np.all(
        trace(A, '10011') == reduce(np.kron, [a3, a2]) * np.trace(a4) *
        np.trace(a1) * np.trace(a0))
    assert np.all(
        trace(A, '10110') == reduce(np.kron, [a3, a0]) * np.trace(a2) *
        np.trace(a1) * np.trace(a4))
    assert np.all(
        trace(A, '11010') == reduce(np.kron, [a2, a0]) * np.trace(a4) *
        np.trace(a1) * np.trace(a3))
    assert np.all(
        trace(A, '11100') == reduce(np.kron, [a1, a0]) * np.trace(a4) *
        np.trace(a3) * np.trace(a2))
    assert np.all(
        trace(A, '11110') == a0 * np.trace(a4) * np.trace(a3) * np.trace(a2) *
        np.trace(a1))
    assert np.all(
        trace(A, '11101') == a1 * np.trace(a4) * np.trace(a3) * np.trace(a2) *
        np.trace(a0))
    assert np.all(
        trace(A, '11011') == a2 * np.trace(a4) * np.trace(a3) * np.trace(a1) *
        np.trace(a0))
    assert np.all(
        trace(A, '10111') == a3 * np.trace(a4) * np.trace(a2) * np.trace(a1) *
        np.trace(a0))
    assert np.all(
        trace(A, '01111') == a4 * np.trace(a3) * np.trace(a2) * np.trace(a1) *
        np.trace(a0))
    assert np.all(trace(A, '11111') == np.trace(A))
