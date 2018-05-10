# -*- coding: utf-8 -*-
import copy
import numpy as np
from scipy import interpolate
from scipy.special import erf, sinc
import matplotlib.pyplot as plt

def _comb_domain(a_domain, b_domain):
    start = min(a_domain[0], b_domain[0])
    stop = max(a_domain[1], b_domain[1])
    start = max(a_domain[0], b_domain[0]) if start == -np.inf else start
    stop = min(a_domain[1], b_domain[1]) if stop == np.inf else stop
    domain = (start, stop)
    return domain

def _comb_outside(a_domain, b_domain, a_outside, b_outside):
    a = a_outside[0] if a_domain[0] <= b_domain[0] else b_outside[0]
    b = a_outside[1] if a_domain[1] >= b_domain[1] else b_outside[1]
    return (a, b)

class Waveform():
    def __init__(self, domain=(0,1), outside=(0,0)):
        '''
        domain : 定义域
        outside: 定义域之外的默认值
        '''
        self._domain = domain
        self._calc_domain = (-np.inf, np.inf)
        self._outside = outside
        self._time_shift = 0
        self.calc = lambda x : 0

    def _mask(self, x):
        mask = (x>self._calc_domain[0])*(x<self._calc_domain[1])
        fmask = (x<=self._calc_domain[0])
        bmask = (x>=self._calc_domain[1])
        return fmask, mask, bmask

    def __a_point_in_calc_domain(self):
        if self._calc_domain[0] == -np.inf and self._calc_domain[1] == np.inf:
            return 0
        elif self._calc_domain[0] == -np.inf:
            return self._calc_domain[1] - 1
        elif self._calc_domain[1] == np.inf:
            return self._calc_domain[0] + 1
        else:
            return 0.5*(self._calc_domain[0]+self._calc_domain[1])

    def _calc(self, x):
        fmask, mask, bmask = self._mask(x-self._time_shift)
        x = mask*(x-self._time_shift)+self.__a_point_in_calc_domain()*(fmask+bmask)
        return fmask*self._outside[0] + bmask*self._outside[1] + mask*self.calc(x)

    def generateData(self, sampleRate, with_x=False):
        x = np.arange(self._domain[0], self._domain[1], 1.0/sampleRate)
        if with_x:
            return x, self._calc(x)
        else:
            return self._calc(x)

    def _comb_waveform(self, other):
        domain = _comb_domain(self._domain, other._domain)
        outside = _comb_outside(self._domain, other._domain, self._outside, other._outside)
        w = Waveform(domain=domain, outside=outside)
        start = min(self._calc_domain[0], other._calc_domain[0])
        stop = max(self._calc_domain[1], other._calc_domain[1])
        w._calc_domain = (start, stop)
        #w._calc_domain = self._comb_calc_domain(other)
        #w._time_shift = self._time_shift
        return w

    def __call__(self, x):
        return self._calc(x)

    def __add__(self, other):
        if isinstance(other, Waveform):
            w = self._comb_waveform(other)
            w.calc = lambda x : self._calc(x) + other._calc(x)
            w._outside = (self._outside[0]+other._outside[0], self._outside[1]+other._outside[1])
            return w
        else:
            return other + self

    def __radd__(self, v):
        #w = copy.deepcopy(self)
        w = Waveform(domain=self._domain, outside=self._outside)
        w.calc = lambda x : v + self._calc(x)
        w._outside = (self._outside[0]+v, self._outside[1]+v)
        return w

    def __sub__(self, other):
        if isinstance(other, Waveform):
            w = self._comb_waveform(other)
            w.calc = lambda x : self._calc(x) - other._calc(x)
            w._outside = (self._outside[0]-other._outside[0], self._outside[1]-other._outside[1])
            return w
        else:
            return - other + self

    def __rsub__(self, v):
        #w = copy.deepcopy(self)
        w = Waveform(domain=self._domain, outside=self._outside)
        w.calc = lambda x : v - self._calc(x)
        w._outside = (v-self._outside[0], v-self._outside[1])
        return w

    def __mul__(self, other):
        if isinstance(other, Waveform):
            w = self._comb_waveform(other)
            w.calc = lambda x : self._calc(x) * other._calc(x)
            w._outside = (self._outside[0]*other._outside[0], self._outside[1]*other._outside[1])
            return w
        else:
            return other * self

    def __rmul__(self, v):
        #w = copy.deepcopy(self)
        w = Waveform(domain=self._domain, outside=self._outside)
        w.calc = lambda x : v * self._calc(x)
        w._outside = (self._outside[0]*v, self._outside[1]*v)
        return w

    def __truediv__(self, other):
        if isinstance(other, Waveform):
            w = self._comb_waveform(other)
            w.calc = lambda x : self._calc(x) / other._calc(x)
            w._outside = (self._outside[0]*other._outside[0], self._outside[1]*other._outside[1])
            return w
        else:
            return (1/other) * self

    def __rtruediv__(self, v):
        #w = copy.deepcopy(self)
        w = Waveform(domain=self._domain, outside=self._outside)
        w.calc = lambda x : v / self._calc(x)
        w._outside = (v/self._outside[0], v/self._outside[1])
        return w

    def __pow__(self, v):
        #w = copy.deepcopy(self)
        w = Waveform(domain=self._domain, outside=self._outside)
        w.calc = lambda x : self._calc(x)**v
        w._outside = (self._outside[0]**v, self._outside[1]**v)
        return w

    def __pos__(self):
        return self

    def __neg__(self):
        #w = copy.deepcopy(self)
        w = Waveform(domain=self._domain, outside=self._outside)
        w.calc = lambda x : - self._calc(x)
        w._outside = (-self._outside[0], -self._outside[1])
        return w

    def __abs__(self):
        #w = copy.deepcopy(self)
        w = Waveform(domain=self._domain, outside=self._outside)
        w.calc = lambda x : abs(self._calc(x))
        w._outside = (abs(self._outside[0]), abs(self._outside[1]))
        return w

    def __or__(self, other):
        w = Waveform((self._domain[0], self._domain[1]+other.len()))
        w._time_shift = self._time_shift
        w._outside = (self._outside[0], other._outside[1])
        #w.calc = lambda x: self._calc(x) if x < self._domain[1] else other._calc(x-self._domain[1]+other._domain[0])
        w.calc = lambda x: self._calc(x) * (x < self._domain[1]) + other._calc(x-self._domain[1]+other._domain[0]) * (x >= self._domain[1])
        return w

    def __xor__(self, n):
        n = int(n)
        if n <= 1:
            return self
        w = copy.deepcopy(self)
        #w = Waveform(domain=self._domain, outside=self._outside)
        for i in range(n-1):
            w = w | self
        return w

    def __rshift__(self, t):
        w = copy.deepcopy(self)
        w._time_shift = self._time_shift + t
        w._domain = (self._domain[0]+t, self._domain[1]+t)
        w._calc_domain = (self._calc_domain[0], self._calc_domain[1])
        return w

    def __lshift__(self, t):
        return self >> (-t)

    def len(self):
        return self._domain[1] - self._domain[0]

    def overwrite(self, other):
        w = self._comb_waveform(other)
        w.calc = lambda x : other._calc(x) * (x >= other._domain[0])*( x <= other._domain[1]) \
                          + self._calc(x) * ((x >= other._domain[0])+( x <= other._domain[1]))
        return w

    def set_range(self, t1, t2):
        self._domain = (t1, t2)
        return self

    def plot(self, n=1000):
        sampleRate = n/self.len()
        x, y = self.generateData(sampleRate, with_x=True)
        plt.plot(x, y)

class DC(Waveform):
    def __init__(self, offset, length=0, range=(0,1)):
        if length <= 0:
            self.start = range[0]
            self.stop = range[1]
        else:
            self.start = 0
            self.stop = length
        super(DC, self).__init__(domain=(self.start, self.stop))
        self._DC = offset
        self.calc = lambda x: self._DC * (x > self.start) * (x < self.stop)

    #def _calc(self, x):
    #    x = x - self._time_shift
    #    return self._DC * (x > self.start) * (x < self.stop)

class Interpolation(Waveform):
    def __init__(self, x, y, interpolation='linear', **kw):
        super(Interpolation, self).__init__(domain = (x[0], x[-1]), **kw)
        self.xy = (x,y)
        self.calc = interpolate.interp1d(x, y, kind=interpolation)
        self._calc_domain = self._domain

class Step(Waveform):
    def __init__(self, width):
        super(Step, self).__init__(domain=(-0.5*width,0.5*width), outside=(0,1))
        self.width = width
        self.calc = lambda x: (erf(5*x/width)+1)/2
        #self.calc = lambda t: a + (b - a) / (1 + np.exp(-(20*t)/width))

class Gaussian(Waveform):
    def __init__(self, width):
        super(Gaussian, self).__init__(domain=(-0.5*width,0.5*width))
        self.width = width
        c = self.width/(4*np.sqrt(2*np.log(2)))
        self.calc = lambda x: np.exp(-0.5*(x/c)**2)

class Sin(Waveform):
    def __init__(self, w, phi=0):
        super(Sin, self).__init__(domain=(-np.inf, np.inf))
        self.calc = lambda t: np.sin(w*t+phi)

class Cos(Waveform):
    def __init__(self, w, phi=0):
        super(Cos, self).__init__(domain=(-np.inf, np.inf))
        self.calc = lambda t: np.cos(w*t+phi)

class Sinc(Waveform):
    def __init__(self, a):
        super(Sinc, self).__init__(domain=(-np.inf, np.inf))
        self.calc = lambda t: sinc(a*t)

__all__ = ['Waveform', 'DC', 'Interpolation', 'Step', 'Gaussian', 'Sin', 'Cos', 'Sinc']

if __name__ == "__main__":
    w = (0.7*Step(0.7)<<1) - (0.2*Step(0.2)) - (0.5*Step(0.5)>>1)
    readout = 0.2*Gaussian(0.05) << 0.11
    pulse = Gaussian(0.3)
    buff = DC(-0.2, 0.1)
    m = (0.5*Gaussian(0.3) << 1) + Gaussian(0.3) + (Gaussian(0.3)/2 >> 0.7)
    squid = Interpolation(x=[0,0.1,0.2,0.8,0.9,1,1.2], y=[0,0,0.6,0.8,-0.2,0,0]) << 1
    gate = (Step(0.2) << 0.5) - (Step(0.2) >> 0.5)
    sqA = DC(1, 0.3)
    sq = sqA >> 0.5
    sqB = (sqA >> 0.5) + (sqA << 0.8)
    igauss = 1 - 1 / (3*Gaussian(0.5) + 1)

    ((pulse ^ 3) + 6).set_range(-1.5,1.5).plot()
    ((0.5*pulse | buff | 0.7*pulse | buff | pulse) + 4).set_range(-1.5,1.5).plot()
    (m+2).set_range(-1.5,1.5).plot()
    ((m*Sin(40*np.pi))**2).set_range(-1.5,1.5).plot(2000)
    (m*Cos(40*np.pi) - 2).set_range(-1.5,1.5).plot()
    (( 0.5*gate << 0.6)*Cos(0.5e2*np.pi) - 4).set_range(-1.5,1.5).plot()
    (w+readout-6).set_range(-1.5,1.5).plot()
    (squid-8).set_range(-1.5,1.5).plot()
    (sq-10).set_range(-1.5,1.5).plot()
    (sq-10.3+0).set_range(-1.5,1.5).plot()
    x,y = sq.set_range(-1.5,1.5).generateData(sampleRate=2000, with_x=True)
    plt.plot(x,y-10.6)
    (igauss-12).set_range(-1.5,1.5).plot()
    (sqA-14).set_range(-1.5,1.5).plot()
    (sqB-16).set_range(-1.5,1.5).plot()

    #pulse.set_range(-1.5,1.5).plot()

    sampleRate = 10e1
    #x,y = (m+1).generateData(sampleRate)
    #plt.plot(x, y, '.', label='w1|w2')

    plt.legend()
    plt.show()
