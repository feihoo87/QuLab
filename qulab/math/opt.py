import functools

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize


def get_initial_simplex(start, senstive=None):
    if senstive is None:
        senstive = np.ones(len(start))

    initial_simplex = [list(start)]
    for i, v in enumerate(senstive):
        row = list(start)
        row[i] += v
        initial_simplex.append(row)
    return np.asarray(initial_simplex)


def parameter_filter(x, dec=None, high=None, low=None):
    if dec is not None:
        x = np.asarray([np.round(a, decimals=d) for a, d in zip(x, dec)])
    if high is None and low is None:
        return x
    return x.clip(low, high)


def optimize(target,
             start,
             senstive=None,
             dec=None,
             high=None,
             low=None,
             print_info=False):
    """
    
    target: 目标函数
    start: 起始点
    senstive: list 敏感度
    dec: list 小数位数
    high: list 上限
    low: list 下限
    print_info: bool
    """

    optimizedTargetValue = None

    @functools.lru_cache()
    def cache_target(*x):
        return target(*x)

    def f(x):
        nonlocal optimizedTargetValue
        x = parameter_filter(x, dec, high, low)
        ret = cache_target(*x)
        if print_info:
            print('.', end='')
        if optimizedTargetValue is None or optimizedTargetValue > ret:
            optimizedTargetValue = ret
            if print_info:
                print('o')
                print(x, ret, end='   ')
        return ret

    ret = minimize(
        f,
        start,
        method='Nelder-Mead',
        options={'initial_simplex': get_initial_simplex(start, senstive)})

    if print_info:
        print('\n', cache_target.cache_info())

    ret['x'] = parameter_filter(ret['x'], dec, high, low)

    return ret
