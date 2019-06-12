from qulab.math.prime import *
from itertools import islice


def test_is_prime():
    assert is_prime(2)
    assert is_prime(3)
    assert not is_prime(4)
    assert is_prime(5)
    assert not is_prime(6)
    assert is_prime(7)
    assert not is_prime(9)
    assert is_prime(24251)
    assert is_prime(1373677)
    assert not is_prime(1373659)
    assert is_prime(9080213)
    assert is_prime(4759123151)
    assert is_prime(2152302898771)
    assert is_prime(3317044064679887385962123)
    assert 3825123056546413057 in Primes()


def test_primePi():
    assert primePi(1) == 0
    assert primePi(2) == 1
    assert primePi(10) == 4
    assert primePi(100) == 25
    assert primePi(1000) == 168
    assert primePi(10000) == 1229
    assert primePi(100000) == 9592
    assert primePi(1000000) == 78498
    assert primePi(10000000) == 664579
    #assert primePi(100000000) == 5761455


def test_prime():
    assert prime(1000) == 7919
    assert prime(10000) == 104729
    assert prime(100000) == 1299709
    assert prime(1000000) == 15485863
    assert prime(10000000) == 179424673
    #assert prime(100000000) == 2038074743


def test_Primes():
    assert list(islice(Primes(), 25)) == [
        2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67,
        71, 73, 79, 83, 89, 97
    ]

    assert list(islice(Primes().less_than(100), 25)) == [
        97, 89, 83, 79, 73, 71, 67, 61, 59, 53, 47, 43, 41, 37, 31, 29, 23, 19,
        17, 13, 11, 7, 5, 3, 2
    ]
