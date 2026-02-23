import numpy as np


def _rot(theta, v):
    x, y, z = np.asarray(v) / np.sqrt(np.sum(np.asarray(v)**2))
    c, s = np.cos(theta), np.sin(theta)

    return np.array([[
        c + (1 - c) * x**2, (1 - c) * x * y - s * z, (1 - c) * x * z + s * y
    ], [(1 - c) * x * y + s * z, c + (1 - c) * y**2, (1 - c) * y * z - s * x],
                     [(1 - c) * x * z - s * y, (1 - c) * y * z + s * x,
                      c + (1 - c) * z**2]])


def rot_round(x, y, z, v=[0, 0, 1], theta=0, c=[0, 0, 0]):
    """
    Rotate a point (x, y, z) around a vector v by an angle theta

    Parameters
    ----------
    x, y, z: coordinates of the point to be rotated
    v: vector to rotate around
    theta: angle to rotate by (in radians)
    c: center of rotation

    Returns
    -------
    ret: rotated coordinates
    """
    ret = (np.array([x, y, z]).T - np.array(c)) @ _rot(theta, v) + np.array(c)
    return ret.T


def projection(x, y, z, d0=1):
    """
    Project a point (x, y, z) onto a plane at z = 0

    Parameters
    ----------
    x, y, z: coordinates of the point to be projected
    d0: distance from the camera to the plane

    Returns
    -------
    ret: projected coordinates
    """
    d = np.sqrt(x**2 + y**2 + z**2)
    return x * d0 / (d0 - z), y * d0 / (d0 - z), d
