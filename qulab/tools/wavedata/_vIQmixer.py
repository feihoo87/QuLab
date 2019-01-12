import numpy as np
from ._wavedata import *


class vIQmixer(object):
    '''virtual IQ mixer'''

    def __init__(self):
        self.LO_freq = None
        # _I, _Q 表示输入的I, Q
        self._I = None
        self._Q = None
        # __I, __Q 表示校准之后的I, Q
        self.__I = None
        self.__Q = None
        self._cali_amp_I = (1,0)
        self._cali_amp_Q = (1,0)
        self._cali_phi = (0,0) #弧度
        self.cali_array = None
        self._RF = None

    def set_IQ(self,I=0,Q=0):
        '''I/Q, at least one Wavedata class'''
        self._I = I
        self._Q = Q
        if I == 0:
            self._I = 0*Q
        elif Q == 0:
            self._Q = 0*I
        assert isinstance(self._I,Wavedata) and isinstance(self._Q,Wavedata)
        assert self._I.size==self._Q.size and self._I.sRate==self._Q.sRate
        self.len = self._I.len
        self.sRate = self._I.sRate
        return self

    def set_LO(self,LO_freq):
        self.LO_freq = LO_freq
        return self

    def set_Cali(self,cali_array=None,DEG=True):
        '''cali_array: 2x3 array ;
        两行分别代表I/Q的校准系数；
        三列分别代表I/Q的 振幅系数、振幅补偿、相位补偿(默认角度)'''
        if cali_array is None:
            cali_array = [[1,0,0],
                          [1,0,0]]
        _cali_array = np.array(cali_array)
        self.cali_array = _cali_array
        self._cali_amp_I = _cali_array[0,:2]
        self._cali_amp_Q = _cali_array[1,:2]
        if DEG:
            self._cali_phi = _cali_array[:,2]*np.pi/180  #转为弧度
        else:
            self._cali_phi = _cali_array[:,2]
        self.__Cali_IQ()
        return self

    def __Cali_IQ(self):
        scale_i, offset_i = self._cali_amp_I
        scale_q, offset_q = self._cali_amp_Q
        self.__I = scale_i * self._I + offset_i
        self.__Q = scale_q * self._Q + offset_q

    def UpConversion(self):
        '''需要先 set_IQ, set_LO, set_Cali, 再使用此方法'''
        cali_phi_i, cali_phi_q = self._cali_phi
        rf_wd = self.__I * Sin(2*np.pi*self.LO_freq,cali_phi_i,self.len,self.sRate) + \
                self.__Q * Cos(2*np.pi*self.LO_freq,cali_phi_q,self.len,self.sRate)
        self._RF = rf_wd
        return self

    @classmethod
    def up_conversion(cls,LO_freq,I=0,Q=0,cali_array=None):
        '''快速配置并上变频'''
        vIQ=cls().set_LO(LO_freq).set_IQ(I,Q).set_Cali(cali_array).UpConversion()
        return vIQ._RF
