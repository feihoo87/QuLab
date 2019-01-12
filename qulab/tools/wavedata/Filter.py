import numpy as np
from ._wavedata import *

def WGN(w, snr):
    '''White Gaussian Noise: 向波形w中添加一个信噪比为 snr dB 的高斯白噪声；
    返回添加噪声后的波形，Wavedata类'''
    assert isinstance(w,Wavedata)
    x=w.data
    snr = 10**(snr/10.0)
    xpower = np.sum(x**2)/len(x)
    npower = xpower / snr
    n = np.random.randn(len(x)) * np.sqrt(npower)
    data = x + n
    return Wavedata(data,w.sRate)
