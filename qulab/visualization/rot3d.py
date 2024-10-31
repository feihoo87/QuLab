import numpy as np
from scipy.linalg import expm


def _rot(theta, v):
    x, y, z = np.asarray(v) / np.sqrt(np.sum(np.asarray(v)**2))
    c, s = np.cos(theta), np.sin(theta)

    return np.array([[
        c + (1 - c) * x**2, (1 - c) * x * y - s * z, (1 - c) * x * z + s * y
    ], [(1 - c) * x * y + s * z, c + (1 - c) * y**2, (1 - c) * y * z - s * x],
                     [(1 - c) * x * z - s * y, (1 - c) * y * z + s * x,
                      c + (1 - c) * z**2]])


def rot_round(x, y, z, v=[0, 0, 1], theta=0, c=[0, 0, 0]):
    ret = (np.array([x, y, z]).T - np.array(c)) @ _rot(theta, v) + np.array(c)
    return ret.T


def projection(x, y, z, y0=1):
    d = np.sqrt(x**2 + y**2 + z**2)
    return x * y0 / y, z * y0 / y, d
