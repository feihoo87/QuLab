import asyncio

import numpy as np

from qulab.math import optimize


def target(x, y, z):
    return (x - 1)**2 + (y + np.e)**2 + (z - np.pi)**2


async def async_target(x, y, z):
    await asyncio.sleep(0.001)
    return target(x, y, z)


def test_optimize():
    ret = optimize(target,
                   start=[0, 0, 0],
                   senstive=[0.1, 0.1, 0.1],
                   dec=[2, 5, 7])
    assert np.all(np.abs(ret['x'] - np.array([1., -np.e, np.pi])) < 1e-5)


def test_optimize_async():
    ret = optimize(async_target,
                   start=[0, 0, 0],
                   senstive=[0.1, 0.1, 0.1],
                   dec=[2, 5, 7])
    assert np.all(np.abs(ret['x'] - np.array([1., -np.e, np.pi])) < 1e-5)
