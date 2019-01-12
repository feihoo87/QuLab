import numpy as np
import matplotlib.pyplot as plt
from scipy import interpolate
from scipy.fftpack import fft,ifft
from scipy.signal import chirp,sweep_poly

__all__ = ['Wavedata', 'Blank', 'DC', 'Triangle', 'Gaussian', 'CosPulse', 'Sin',
    'Cos', 'Sinc', 'Interpolation', 'Chirp', 'Sweep_poly']

class Wavedata(object):

    def __init__(self, data = [], sRate = 1):
        '''给定序列和采样率，构造Wavedata'''
        self.data = np.array(data)
        self.sRate = sRate

    @staticmethod
    def generateData(timeFunc, domain=(0,1), sRate=1e2):
        '''给定函数、定义域、采样率，生成data序列'''
        length = np.around(abs(domain[1]-domain[0]) * sRate).astype(int) / sRate
        _domain = min(domain), (min(domain)+length)
        dt = 1/sRate
        _timeFunc = lambda x: timeFunc(x) * (x > _domain[0]) * ( x < _domain[1])
        x = np.arange(_domain[0]+dt/2, _domain[1], dt)
        data = np.array(_timeFunc(x))
        return data

    @classmethod
    def init(cls, timeFunc, domain=(0,1), sRate=1e2):
        '''给定函数、定义域、采样率，生成Wavedata类'''
        data = cls.generateData(timeFunc,domain,sRate)
        return cls(data,sRate)

    def _blank(self,length=0):
        n = np.around(abs(length)*self.sRate).astype(int)
        data = np.zeros(n)
        return data

    @property
    def x(self):
        '''返回波形的时间列表'''
        dt=1/self.sRate
        x = np.arange(dt/2, self.len, dt)
        return x

    @property
    def len(self):
        '''返回波形长度'''
        length = self.size/self.sRate
        return length

    @property
    def size(self):
        '''返回波形点数'''
        size = len(self.data)
        return size

    def setLen(self,length):
        '''设置长度，增大补0，减小截取'''
        n = np.around(abs(length)*self.sRate).astype(int)
        return self.setSize(n)

    def setSize(self,size):
        '''设置点数，增多补0，减少截取'''
        n = np.around(size).astype(int)
        s = self.size
        if n > s:
            append_data=np.zeros(n-s)
            self.data = np.append(self.data, append_data)
        else:
            self.data = self.data[:n]
        return self

    def __call__(self, t):
        '''w(t) 返回某个时间点的最近邻值'''
        dt = 1/self.sRate
        idx = np.around(t/dt-0.5).astype(int)
        return self.data[idx]

    def __pos__(self):
        '''正 +w'''
        return self

    def __neg__(self):
        '''负 -w'''
        w = Wavedata(-self.data, self.sRate)
        return w

    def __abs__(self):
        '''绝对值 abs(w)'''
        w = Wavedata(np.abs(self.data), self.sRate)
        return w

    def __rshift__(self, t):
        '''右移 w>>t 长度不变'''
        if abs(t)>self.len:
            raise TypeError('shift is too large !')
        shift_data=self._blank(abs(t))
        left_n = self.size-len(shift_data)
        if t>0:
            data = np.append(shift_data, self.data[:left_n])
        else:
            data = np.append(self.data[-left_n:], shift_data)
        w = Wavedata(data, self.sRate)
        return w

    def __lshift__(self, t):
        '''左移 t<<w 长度不变'''
        return self >> (-t)

    def __or__(self, other):
        '''或 w|o 串联波形'''
        assert isinstance(other,Wavedata)
        assert self.sRate == other.sRate
        data = np.append(self.data,other.data)
        w = Wavedata(data, self.sRate)
        return w

    def __xor__(self, n):
        '''异或 w^n 串联n个波形'''
        n = int(n)
        if n <= 1:
            return self
        else:
            data = list(self.data)*n
            w = Wavedata(data, self.sRate)
            return w

    def __pow__(self, v):
        '''幂 w**v 波形值的v次幂'''
        data = self.data ** v
        w = Wavedata(data, self.sRate)
        return w

    def __add__(self, other):
        '''加 w+o 波形值相加，会根据类型判断'''
        if isinstance(other,Wavedata):
            assert self.sRate == other.sRate
            size = max(self.size, other.size)
            self.setSize(size)
            other.setSize(size)
            data = self.data + other.data
            w = Wavedata(data, self.sRate)
            return w
        else:
            return other + self

    def __radd__(self, v):
        '''加 v+w 波形值加v，会根据类型判断'''
        data = self.data +v
        w = Wavedata(data, self.sRate)
        return w

    def __sub__(self, other):
        '''减 w-o 波形值相减，会根据类型判断'''
        return self + (- other)

    def __rsub__(self, v):
        '''减 v-w 波形值相减，会根据类型判断'''
        return v + (-self)

    def __mul__(self, other):
        '''乘 w*o 波形值相乘，会根据类型判断'''
        if isinstance(other,Wavedata):
            assert self.sRate == other.sRate
            size = max(self.size, other.size)
            self.setSize(size)
            other.setSize(size)
            data = self.data * other.data
            w = Wavedata(data, self.sRate)
            return w
        else:
            return other * self

    def __rmul__(self, v):
        '''乘 v*w 波形值相乘，会根据类型判断'''
        data = self.data * v
        w = Wavedata(data, self.sRate)
        return w

    def __truediv__(self, other):
        '''除 w/o 波形值相除，会根据类型判断'''
        if isinstance(other,Wavedata):
            assert self.sRate == other.sRate
            size = max(self.size, other.size)
            self.setSize(size)
            other.setSize(size)
            data = self.data / other.data
            w = Wavedata(data, self.sRate)
            return w
        else:
            return (1/other) * self

    def __rtruediv__(self, v):
        '''除 v/w 波形值相除，会根据类型判断'''
        data = v / self.data
        w = Wavedata(data, self.sRate)
        return w

    def convolve(self, other, mode='same'):
        '''卷积
        mode: full, same, valid'''
        if isinstance(other,Wavedata):
            _kernal = other.data
        elif isinstance(other,(np.ndarray,list)):
            _kernal = np.array(other)
        k_sum = sum(_kernal)
        kernal = _kernal / k_sum   #归一化kernal，使卷积后的波形总幅度不变
        data = np.convolve(self.data,kernal,mode)
        w = Wavedata(data, self.sRate)
        return w

    def FFT(self, mode='amp',half=True,**kw):
        '''FFT'''
        sRate = self.size/self.sRate
        # 对于实数序列的FFT，正负频率的分量是相同的
        # 对于双边谱，即包含负频率成分的，除以size N 得到实际振幅
        # 对于单边谱，即不包含负频成分，实际振幅是正负频振幅的和，所以除了0频成分其他需要再乘以2
        fft_data = fft(self.data,**kw)/self.size
        if mode == 'amp':
            data =np.abs(fft_data)
        elif mode == 'phase':
            data =np.angle(fft_data,deg=True)
        elif mode == 'real':
            data =np.real(fft_data)
        elif mode == 'imag':
            data =np.imag(fft_data)
        elif mode == 'complex':
            data = fft_data
        if half:
            #size N为偶数时，取N/2；为奇数时，取(N+1)/2
            index = int((len(data)+1)/2)-1
            data = data[:index]
            data[1:] = data[1:]*2 #非0频成分乘2
        w = Wavedata(data, sRate)
        return w

    def getFFT(self,freq,mode='complex',**kw):
        ''' 获取指定频率的FFT分量；
        freq: 为一个频率值或者频率的列表，
        返回值: 是对应mode的一个值或列表'''
        freq_array=np.array(freq)
        fft_w = self.FFT(mode=mode,half=True,**kw)
        index_freq = np.around(freq_array*fft_w.sRate).astype(int)
        res_array = fft_w.data[index_freq]
        return res_array

    def high_resample(self,sRate):
        '''提高高采样率重新采样'''
        assert sRate > self.sRate
        #提高采样率时，新起始点会小于原起始点，新结束点大于原结束点
        #为了插值函数成功插值，在序列前后各加一个点，增大插值范围
        dt = 1/self.sRate
        x = np.arange(-dt/2, self.len+dt, dt)
        _y = np.append(0,self.data)
        y = np.append(_y,0)
        timeFunc = interpolate.interp1d(x,y,kind='nearest')
        domain = (0,self.len)
        w = Wavedata.init(timeFunc,domain,sRate)
        return w

    def low_resample(self,sRate):
        '''降低采样率重新采样'''
        assert sRate < self.sRate
        #降低采样率时，新起始点会大于原起始点，新结束点小于原结束点，
        #插值定义域不会超出，所以不用处理
        x = self.x
        y = self.data
        timeFunc = interpolate.interp1d(x,y,kind='linear')
        domain = (0,self.len)
        w = Wavedata.init(timeFunc,domain,sRate)
        return w

    def resample(self,sRate):
        '''改变采样率重新采样'''
        if sRate == self.sRate:
            return self
        elif sRate > self.sRate:
            return self.high_resample(sRate)
        elif sRate < self.sRate:
            return self.low_resample(sRate)

    def normalize(self):
        '''归一化波形，使其分布在(-1,+1)'''
        self.data = self.data/max(abs(self.data))
        return self

    def plot(self, *arg, isfft=False, **kw):
        '''对于FFT变换后的波形数据，包含0频成分，x从0开始；
        使用isfft=True会去除了x的偏移，画出的频谱更准确'''
        ax = plt.gca()
        if isfft:
            dt=1/self.sRate
            x = np.arange(0, self.len-dt/2, dt)
            ax.plot(x, self.data, *arg, **kw)
        else:
            ax.plot(self.x, self.data, *arg, **kw)


def Blank(width=0, sRate=1e2):
    timeFunc = lambda x: 0
    domain=(0, width)
    return Wavedata.init(timeFunc,domain,sRate)

def DC(width=0, sRate=1e2):
    timeFunc = lambda x: 1
    domain=(0, width)
    return Wavedata.init(timeFunc,domain,sRate)

def Triangle(width=1, sRate=1e2):
    timeFunc = lambda x: 1-np.abs(2/width*x)
    domain=(-0.5*width,0.5*width)
    return Wavedata.init(timeFunc,domain,sRate)

def Gaussian(width=1, sRate=1e2):
    c = width/(4*np.sqrt(2*np.log(2)))
    timeFunc = lambda x: np.exp(-0.5*(x/c)**2)
    domain=(-0.5*width,0.5*width)
    return Wavedata.init(timeFunc,domain,sRate)

def CosPulse(width=1, sRate=1e2):
    timeFunc = lambda x: (np.cos(2*np.pi/width*x)+1)/2
    domain=(-0.5*width,0.5*width)
    return Wavedata.init(timeFunc,domain,sRate)

def Sin(w, phi=0, width=0, sRate=1e2):
    timeFunc = lambda t: np.sin(w*t+phi)
    domain=(0,width)
    return Wavedata.init(timeFunc,domain,sRate)

def Cos(w, phi=0, width=0, sRate=1e2):
    timeFunc = lambda t: np.cos(w*t+phi)
    domain=(0,width)
    return Wavedata.init(timeFunc,domain,sRate)

def Sinc(a, width=1, sRate=1e2):
    timeFunc = lambda t: np.sinc(a*t)
    domain=(-0.5*width,0.5*width)
    return Wavedata.init(timeFunc,domain,sRate)

def Interpolation(x, y, sRate=1e2, kind='linear'):
    '''参考scipy.interpolate.interp1d 插值'''
    timeFunc = interpolate.interp1d(x, y, kind=kind)
    domain = (x[0], x[-1])
    return Wavedata.init(timeFunc,domain,sRate)

def Chirp(width, f0, f1, sRate=1e2, method='linear', phi=0):
    '''参考scipy.signal.chirp 啁啾'''
    t1 = width # 结束点
    timeFunc = lambda t: chirp(t, f0, t1, f1, method=method, phi=phi, )
    domain = (0,t1)
    return Wavedata.init(timeFunc,domain,sRate)

def Sweep_poly(width, poly, sRate=1e2, phi=0):
    '''参考scipy.signal.sweep_poly 多项式频率'''
    timeFunc = lambda t: sweep_poly(t, poly, phi=0)
    domain = (0,width)
    return Wavedata.init(timeFunc,domain,sRate)


if __name__ == "__main__":
    a=Sin(w=1, width=10, phi=0, sRate=1000)
    b=Gaussian(2,sRate=1000)
    c=Blank(1,sRate=1000)

    m=(0.5*a|c|b|c|b+1|c|a+0.5).setLen(20)>>5
    n=m.convolve(b)
    m.plot()
    n.plot()
    plt.show()
