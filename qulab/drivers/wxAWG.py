# -*- coding: utf-8 -*-
import numpy as np
import visa

from qulab import BaseDriver, QInteger, QList, QOption, QReal


class Driver(BaseDriver):
    support_models = ['wx2184']

    quants = [
        QReal('Sample Rate',
              unit='S/s',
              set_cmd=':FREQ:RAST %(value)g',
              get_cmd=':FREQ:RAST?'),
        QReal('Amp',
              unit='V',
              set_cmd=':VOLT:LEV:AMPL %(value)f',
              get_cmd=':VOLT:LEV:AMPL?'),
        QReal('Offset',
              unit='V',
              set_cmd=':VOLT:LEV:OFFS %(value)f',
              get_cmd=':VOLT:LEV:OFFS?'),
        QReal('Frequency',
              unit='Hz',
              set_cmd=':FREQ %(value)f',
              get_cmd=':FREQ?'),
        QReal('Phase',
              unit='Deg',
              set_cmd=':SIN:PHAS %(value)f',
              get_cmd=':SIN:PHAS?'),
        QOption('Output',
                set_cmd=':OUTP %(option)s',
                get_cmd=':OUTP?',
                options=[('OFF', 'OFF'), ('ON', 'ON')]),
        QInteger(
            'Select_ch',
            value=1,
            unit='',
            set_cmd=':INST:SEL %(value)d',
            get_cmd=':INST:SEL?',
        ),
        #options=[('1', '1'), ('2', '2'), ('3', '3'), ('4', '4')]
        QInteger('Select_trac',
                 value=1,
                 unit='',
                 set_cmd=':TRAC:SEL %(value)d',
                 get_cmd=':TRAC:SEL?'),
    ]

    def dc(self, ch=1, offs=1.0):
        self.write(':INST:SEL CH%d' % ch)
        self.write(':FUNC:MODE FIX')
        self.write(':FUNC:SHAP DC')
        self.write(':DC %f' % offs)
        self.write(':OUTP ON')

    def sin(self, ch=1, freq=2e8, amp=0.5, offs=0.0, phas=0):
        self.write(':INST:SEL CH%d' % ch)
        self.write(':FUNC:MODE FIX')
        self.write(':FUNC:SHAP SIN')
        self.write(':FREQ %f' % freq)
        self.write(':VOLT:LEV:AMPL %f' % amp)
        self.write(':VOLT:LEV:OFFS %f' % offs)
        self.write(':SIN:PHAS %f' % phas)
        self.write(':OUTP ON')

    def reset(self, samplerate=2.3e9):
        self.write('*CLS')
        self.write('*RST')
        #选择特定function
        self.write(':FUNC:MODE USER')
        #设置采样率
        self.write(':FREQ:RAST %d' % samplerate)
        #设置外部时钟
        self.write(':ROSCillator:SOURce EXTernal')
        #清除原有波形
        self.write(':INST:SEL CH1')
        self.write(':TRAC:DEL:ALL')
        self.write(':INST:SEL CH3')
        self.write(':TRAC:DEL:ALL')
        #将几个通道的设置设为同一个，详见manual
        # self.write(':INST:COUPle:STATe ON')
        # self.write(':INIT:CONT OFF')
        # self.write(':TRIG:COUN 1')
        # self.write('enable')

    #创建波形文件
    def crwave(self, segment_num, sample_num):
        self.write(':TRAC:DEF %d,%d' % (segment_num, sample_num))

    #在创建好的波形文件中，写入或者更新具体波形
    def upwave(self, points, ch=1, trac=1):
        pointslen = len(points)
        pointslen2 = 2 * pointslen
        #选择特定function
        self.write(':FUNC:MODE USER')
        #选择特定channel
        self.write(':INST:SEL %d' % ch)
        #定义特定的segment
        self.write(':TRAC:DEF %d,%d' % (trac, pointslen))
        #选择特定的segment
        self.write(':TRAC:SEL %d' % trac)
        #选择模式为SINGLE，（包括DUPLicate，SINGle等，详见manual）
        self.write(':TRAC:MODE SING')
        #写入波形数据
        message = ':TRAC:DATA'  # % (len(str(pointslen2)),pointslen2)
        points = points.clip(-1, 1)
        values = np.zeros(pointslen).astype(np.uint16)
        #乘积选用8191是为了防止最终值大于16383
        values = (points * 8191).astype(np.uint16) + 8192  #.astype(np.uint16)
        byte = np.zeros(pointslen2).astype(np.uint8)
        #将原先的两比特数据点，分割为高低两个比特
        byte[0:pointslen2:2] = (values & 0b11111111).astype(np.uint8)
        byte[1:pointslen2:2] = ((values & 0b11111100000000) >> 8).astype(
            np.uint8)
        #write_binary_value中的message参数不要包括#42048的信息，因为pyvisa可以自动算出结果。详见pyvisa中util.py内的to_binary_block
        #wx2184选用little_endian。这表示程序按照我给的顺序将二进制包写进去
        self.write_binary_values(message,
                                 byte,
                                 datatype='B',
                                 is_big_endian=False,
                                 termination=None,
                                 encoding=None)
        # self.write('enable' )

#运行波形

    def ruwave(self, amp=2, offset=0, ch=1, trac=1, trigdelay=0):
        self.write(':INST:SEL %d' % ch)
        self.write(':VOLT:LEV:AMPL %f' % amp)
        self.write(':VOLT:LEV:OFFS %f' % offset)
        self.write(':TRAC:SEL %d' % trac)
        self.write(':OUTP ON')
        self.write(':INIT:CONT OFF')
        self.write(':TRIG:COUN 1')
        self.write(':TRIG:DEL %d' % trigdelay)

    def ruwave1(self, amp=2, offset=0, ch=1, trac=1):
        self.write(':INST:SEL %d' % ch)
        self.write(':VOLT:LEV:AMPL %f' % amp)
        self.write(':VOLT:LEV:OFFS %f' % offset)
        self.write(':TRAC:SEL %d' % trac)
        self.write(':OUTP ON')
        self.write(':INIT:CONT ON')

    def ruwave2(self, amp=2, ch=1, trac=1):
        self.write(':INST:SEL %d' % ch)
        self.write(':VOLT:LEV:AMPL %f' % amp)
        self.write(':TRAC:SEL %d' % trac)
        self.write(':OUTP ON')
        self.write(':INIT:CONT OFF')
        self.write(':TRIG:COUN 1')
