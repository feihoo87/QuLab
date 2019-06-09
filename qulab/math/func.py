import numpy as np
from scipy.special import sici
from scipy.stats import beta


def get_unit_prefix(value):
    '''
    获取 value 合适的单位前缀，以及相应的倍数

    >>>
        y => 1e-24       Y => 1e24
        z => 1e-21       Z => 1e21
        a => 1e-18       E => 1e18
        f => 1e-15       P => 1e15
        p => 1e-12       T => 1e12
        n => 1e-9        G => 1e9
        u => 1e-6        M => 1e6
        m => 1e-3        k => 1e3

    Returns:
        (prefix, multiple)
    '''
    prefixs = [
        'y', 'z', 'a', 'f', 'p', 'n', 'u', 'm', '', 'k', 'M', 'G', 'T', 'P',
        'E', 'Z', 'Y'
    ]
    x = np.floor(np.log10(value) / 3)
    x = -8 if x < -8 else x
    x = 8 if x > 8 else x
    return prefixs[int(x) + 8], 1000**(x)


def skew(x):
    '''
    计算偏度
    '''
    ret = (x - x.mean()) / x.std(ddof=0)
    return np.mean(ret**3)


def kurtosis(x):
    '''
    计算峰度
    '''
    ret = (x - x.mean()) / x.std(ddof=0)
    return np.mean(ret**4) - 3


def get_probility(x, N, a=0.05):
    '''
    计算 N 此重复实验，事件 A 发生 x 次时，事件 A 的发生概率

    Args:
        x : 事件发生次数
        N : 总实验次数
        a : 设置显著性水平 1-a，默认 0.05

    Returns:
        P, E, std, (low, high)
        事件 A 发生概率 P 的最概然取值、期望、以及其置信区间
    '''
    P = 1.0 * x / N
    E = (x + 1.0) / (N + 2.0)
    std = np.sqrt(E * (1 - E) / (N + 3))
    low = beta.ppf(0.5 * a, x + 1, N - x + 1)
    high = beta.ppf(1 - 0.5 * a, x + 1, N - x + 1)
    return P, E, std, (low, high)


def threshold(data, delta=1e-7):
    '''
    给定一组成双峰分布的数据 data 计算双峰之间的分界值

    Args:
        data : numpy.array
        delta: 精确度，默认 delta = 1e-7
    '''
    threshold = m1 = m2 = data.mean()
    while True:
        g1 = data[data < threshold]
        g2 = data[data > threshold]
        m1 = g1.mean()
        m2 = g2.mean()
        t = (m1 + m2) / 2
        if abs(threshold - t) < delta:
            break
        threshold = t
    return threshold


def get_threshold_visibility(data1, data2):
    '''
    给定两组数据，寻找区分两组数据的临界值，并计算可见度及矫正系数

    Returns:
        tuple:
        visibility : float 可见度
        threshold : float 临界值
        corr : tuple 矫正系数
    
    >>> threshold, visibility, (a, b) = get_threshold_visibility(state0, state1)
    >>> P, E, std, (low, high) = get_probility(np.count_nonzero(data<threshold), len(data))
    >>> P1 = (P - a) / (a + b)
    '''
    lims = [min(data1.min(), data2.min()), max(data1.max(), data2.max())]
    bins = np.linspace(lims[0], lims[1], min(len(data1) + len(data2), 1000))
    y1, _ = np.histogram(data1, bins=bins)
    y2, _ = np.histogram(data2, bins=bins)
    y1 = y1.cumsum() / y1.sum()
    y2 = y2.cumsum() / y2.sum()
    y = np.abs(y1 - y2)
    i = y.argmax()
    return 0.5 * (bins[i] + bins[i + 1]), y[i], (y1[i], y2[i])


def FWHM_of_normal_distribution(std):
    '''
    正态分布的半高宽
    '''
    return 2 * np.sqrt(2 * np.log(2)) * std


def Std_of_norm_from_FWHM(FWHM):
    '''
    给定正态分布的半高宽，计算其标准差
    '''
    return FWHM / (2 * np.sqrt(2 * np.log(2)))


def vonNeumannEntropy(rho):
    '''
    冯诺伊曼熵
    '''
    r = np.real(np.linalg.eigvals(rho))
    return np.sum(-r * np.log(r + (r <= 0)))
