# -*- coding: utf-8 -*-
import struct

import numpy as np
from scipy.special import sici
from scipy.stats import beta


def get_unit_prefix(value):
    '''获取 value 合适的单位前缀，以及相应的倍数

    y => 1e-24       Y => 1e24
    z => 1e-21       Z => 1e21
    a => 1e-18       E => 1e18
    f => 1e-15       P => 1e15
    p => 1e-12       T => 1e12
    n => 1e-9        G => 1e9
    u => 1e-6        M => 1e6
    m => 1e-3        k => 1e3
    '''
    prefixs = [
        'y', 'z', 'a', 'f', 'p', 'n', 'u', 'm', '', 'k', 'M', 'G', 'T', 'P',
        'E', 'Z', 'Y'
    ]
    x = np.floor(np.log10(value) / 3)
    x = -8 if x < -8 else x
    x = 8 if x > 8 else x
    return prefixs[int(x) + 8], 1000**(x)


# 单位转换


def dBmToW(p):
    return 10**(p / 10.0 - 3)


def WTodBm(p):
    return np.log10(p) * 10.0 + 30


def skew(x):
    '''偏度

    在概率论和统计学中，偏度（Skewness）衡量实数随机变量概率分布的不对称性。在数量上，偏度为
    负（负偏态）就意味着在概率密度函数左侧的尾部比右侧的长，绝大多数的值（包括中位数在内）位于
    平均值的右侧。偏度为正（正偏态）就意味着在概率密度函数右侧的尾部比左侧的长，绝大多数的值
    （但不一定包括中位数）位于平均值的左侧。偏度为零就表示数值相对均匀地分布在平均值的两侧，但
    不一定意味着其为对称分布。
    '''
    ret = (x - x.mean()) / x.std(ddof=0)
    return np.mean(ret**3)


def kurtosis(x):
    '''峰度

    在统计学中，峰度（Kurtosis）衡量实数随机变量概率分布的峰态。峰度高就意味着方差增大是由低
    频度的大于或小于平均值的极端差值引起的。
    '''
    ret = (x - x.mean()) / x.std(ddof=0)
    return np.mean(ret**4) - 3


def get_probility(x, N, a=0.05):
    '''计算 N 此重复实验，事件 A 发生 x 次时，事件 A 的发生概率

    x : 事件发生次数
    N : 总实验次数
    a : 设置显著性水平 1-a，默认 0.05

    返回事件 A 发生概率 P 的最概然取值、期望、以及其置信区间
    '''
    P = 1.0 * x / N
    E = (x + 1.0) / (N + 2.0)
    std = np.sqrt(E * (1 - E) / (N + 3))
    low, high = beta.ppf(0.5 * a, x + 1, N - x + 1), beta.ppf(
        1 - 0.5 * a, x + 1, N - x + 1)
    return P, E, std, (low, high)


def threshold(data, delta=1e-7):
    '''给定一组成双峰分布的数据 data 计算双峰之间的分界值

    data : 数据类型 numpy.array
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
    '''给定两组数据，寻找区分两组数据的临界值，并计算可见度及矫正系数'''
    lims = [min(data1.min(), data2.min()), max(data1.max(), data2.max())]
    bins = np.linspace(lims[0], lims[1], min(len(data1) + len(data2), 1000))
    y1, _ = np.histogram(data1, bins=bins)
    y2, _ = np.histogram(data2, bins=bins)
    y1 = y1.cumsum() / y1.sum()
    y2 = y2.cumsum() / y2.sum()
    y = np.abs(y1 - y2)
    i = y.argmax()
    return 0.5 * (bins[i] + bins[i + 1]), y[i], (y1[i], y2[i])


def get_projection_axes(data1, data2):
    v = data1.mean() - data2.mean()
    return v / np.abs(v)


def project_data_into_axes(data, v):
    return np.real(data / v)


def step_t(w1, w2, t0, width, t):
    """
    Step function that goes from w1 to w2 at time t0
    as a function of t.
    """
    return w1 + (w2 - w1) * (t > t0)


def step_t_finite(w1, w2, t0, width, t):
    """
    Step function that goes from w1 to w2 at time t0
    as a function of t, with finite rise time defined
    by the parameter width.
    """
    return w1 + (w2 - w1) / (1 + np.exp(-(t - t0) / width))


def step_t_finite_overshoot(w1, w2, t0, width, t):
    """
    Step function that goes from w1 to w2 at time t0
    as a function of t, with finite rise time and
    and overshoot defined by the parameter width.
    """
    return w1 + (w2 - w1) * (0.5 + sici((t - t0) / width)[0] / (np.pi))


def FWHM_of_normal_distribution(std):
    '''正态分布的半高宽'''
    return 2 * np.sqrt(2 * np.log(2)) * std


def Std_of_norm_from_FWHM(FWHM):
    return FWHM / (2 * np.sqrt(2 * np.log(2)))


def IEEE_488_2_BinBlock(datalist, dtype="int16", is_big_endian=True):
    """将一组数据打包成 IEEE 488.2 标准二进制块

    datalist : 要打包的数字列表
    dtype    : 数据类型
    endian   : 字节序

    返回二进制块, 以及其 'header'
    """
    types = {"b"      : (  int, 'b'), "B"      : (  int, 'B'),
             "h"      : (  int, 'h'), "H"      : (  int, 'H'),
             "i"      : (  int, 'i'), "I"      : (  int, 'I'),
             "q"      : (  int, 'q'), "Q"      : (  int, 'Q'),
             "f"      : (float, 'f'), "d"      : (float, 'd'),
             "int8"   : (  int, 'b'), "uint8"  : (  int, 'B'),
             "int16"  : (  int, 'h'), "uint16" : (  int, 'H'),
             "int32"  : (  int, 'i'), "uint32" : (  int, 'I'),
             "int64"  : (  int, 'q'), "uint64" : (  int, 'Q'),
             "float"  : (float, 'f'), "double" : (float, 'd'),
             "float32": (float, 'f'), "float64": (float, 'd')}

    datalist = np.asarray(datalist)
    datalist.astype(types[dtype][0])
    if is_big_endian:
        endianc = '>'
    else:
        endianc = '<'
    datablock = struct.pack('%s%d%s' % (endianc, len(datalist), types[dtype][1]), *datalist)
    size = '%d' % len(datablock)
    header = '#%d%s' % (len(size),size)

    return header.encode()+datablock, header


if __name__ == '__main__':
    pass
