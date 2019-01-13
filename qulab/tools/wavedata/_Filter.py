import numpy as np
from ._wavedata import Wavedata


class Filter(object):
    """Filter baseclass, filt nothing."""
    def __init__(self):
        super(Filter, self).__init__()

    def process(self,data,sRate):
        return data,sRate

    def filt(self,w):
        assert isinstance(w,Wavedata)
        data,sRate = self.process(w.data,w.sRate)
        return Wavedata(data,sRate)


def series(*arg):
    '''串联多个Filter'''
    def process(data,sRate):
        for f in arg:
            data,sRate = f.process(data,sRate)
        return data,sRate
    F = Filter()
    F.process=process
    return F


def parallel(*arg):
    '''并联多个Filter'''
    def process(data,sRate):
        d_list = [f.process(data,sRate)[0] for f in arg]
        d = np.array(d_list).sum(axis=0)/len(arg)
        return d,sRate
    F = Filter()
    F.process=process
    return F


class WGN(Filter):
    '''White Gaussian Noise adder: 向波形w中添加一个信噪比为 snr dB 的高斯白噪声'''
    def __init__(self, snr):
        super(WGN, self).__init__()
        self.snr = snr

    def process(self,data,sRate):
        x=data
        snr = 10**(self.snr/10.0)
        xpower = np.sum(x**2)/len(x)
        npower = xpower / snr
        n = np.random.randn(len(x)) * np.sqrt(npower)
        _data = x + n
        return _data,sRate
