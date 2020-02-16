import numpy as np
import visa
import logging
log = logging.getLogger(__name__)

from qulab.Driver import wxDriver, QInteger, QOption, QReal



class Driver(wxDriver):
    __log__=log
    support_models = ['wx2184']

    quants = [
        # Arb waveforms frequency
        QReal('Sample Rate',
              value=1e9,
              unit='Sa/s',
              set_cmd=':FREQ:RAST %(value)e',
              get_cmd=':FREQ:RAST?'),

        # Amp, Offset 要在选择通道后设置，每个通道独立
        QReal('Amp', value=1, unit='Vpp', ch=1,
              set_cmd=':INST:SEL %(ch)d;:VOLT:LEV:AMPL %(value)f',
              get_cmd=':INST:SEL %(ch)d;:VOLT:LEV:AMPL?'),
        QReal('Offset', value=0, unit='V', ch=1,
              set_cmd=':INST:SEL %(ch)d;:VOLT:LEV:OFFS %(value)f',
              get_cmd=':INST:SEL %(ch)d;:VOLT:LEV:OFFS?'),

        # 任意波须选USER模式
        QOption('Function Mode', value='Fixed', ch=1,
                set_cmd=':INST:SEL %(ch)d;:FUNC:MODE %(option)s',
                get_cmd=':INST:SEL %(ch)d;:FUNC:MODE?',
                options=[('Fixed', 'FIX'), ('User', 'USER'),
                         ('Sequence', 'SEQ'), ('ASequence', 'ASEQ'),
                         ('Modulation','MOD'), ('Pulse','PULS'),
                         ('Patten','PATT')]),

        ## Function Shape: 只在Fixed模式下才能设置
        QOption('Function Shape', value='Sin', ch=1,
                set_cmd=':INST:SEL %(ch)d;:FUNC:SHAP %(option)s',
                get_cmd=':INST:SEL %(ch)d;:FUNC:SHAP?',
                options=[('Sin', 'SIN'), ('Triangle', 'TRI'),
                         ('Square', 'SQU'), ('Ramp', 'RAMP'),
                         ('Sinc','SINC'), ('Gaussian','GAUS'),
                         ('Exponential','EXP'),('Noise','NOIS'),
                         ('DC','DC')]),

        ## Trace Mode: 只在USER模式，即任意波模式下才能设置
        QOption('Trace Mode', value='Single', ch=1,
                set_cmd=':INST:SEL %(ch)d;:TRAC:MODE %(option)s',
                get_cmd=':INST:SEL %(ch)d;:TRAC:MODE?',
                options=[('Single', 'SING'), ('Duplicate', 'DUPL'),
                         ('Zerode', 'ZER'), ('Combined', 'COMB'),]),

        ## Continuous Mode: 关闭连续模式即为触发模式
        QOption('Continuous Mode', value='OFF', 
                set_cmd=':INIT:CONT %(option)s',
                get_cmd=':INIT:CONT?',
                options=[('OFF', 0), ('ON', 1)]),

        # QInteger('Current CH',value=1,
        #         set_cmd=':INST:SEL %(value)d',
        #         get_cmd=':INST:SEL?',),
        # QInteger('Current Trace',value=1,ch=1,
        #         set_cmd=':INST:SEL %(ch)d;:TRAC:SEL %(value)d',
        #         get_cmd=':INST:SEL %(ch)d;:TRAC:SEL?'),

        QOption('Output', value='OFF', ch=1,
                set_cmd=':INST:SEL %(ch)d;:OUTP %(option)s',
                get_cmd=':INST:SEL %(ch)d;:OUTP?',
                options=[('OFF', 'OFF'), ('ON', 'ON')]),
    ]

    CHs=[1,2,3,4]

    def performOpen(self,):
        super().performOpen()
        self.setValue('Continuous Mode','OFF')
        # self.write(':INIT:GATE:STAT OFF')
        for ch in self.CHs:
            self.setValue('Function Mode','User',ch=ch)
            self.setValue('Trace Mode','Duplicate',ch=ch)

    def crwave(self, ch, segment, length):
        '''创建波形，1/2通道共用内存，3/4通道共用内存，两者独立编号

        Parameters:
            ch: 通道编号，1/2共用内存，3/4共用内存
            segment: 在内存中的片段编号，范围1-32000，即trace编号
            length: 波形长度(点数)，范围192-16(32)e6，必须为16的整数倍，否则报错
        '''
        self.write(':INST:SEL %s'%ch)
        self.write(':TRAC:DEF %d,%d' % (segment, length))

    def delwave(self,ch,segment=1,all=False):
        self.write(':INST:SEL %s'%ch)
        if all:
            self.write(':TRAC:DEL:ALL')
        else:
            self.write(':TRAC:DEL %d' % segment)

    def upwave(self, points, ch=1, trace=1):
        self.write(':INST:SEL %d;:TRAC:SEL %d' % (ch,trace))
        points = points.clip(-1, 1)
        wav = self.build_wave(points)
        self.handle.send_binary_data(':TRAC:DATA', wav)

    # def upwave(self, points, ch=1, trace=1):
    #     self.setValue('Current Trace',trace,ch=ch)
    #     message = ':TRAC:DATA'
    #     values = points.clip(-1, 1)
    #     self.write_binary_values(message,
    #                              values,
    #                              datatype=u'f',
    #                              is_big_endian=False,
    #                              termination=None,
    #                              encoding=None)

    def usewave(self,ch=1,trace=1):
        self.write(':INST:SEL %d;:TRAC:SEL %d' % (ch,trace))

    # #在创建好的波形文件中，写入或者更新具体波形
    # def upwave_wx(self, points, ch=1, trac=1):
    #     pointslen = len(points)
    #     pointslen2 = 2 * pointslen
    #     #选择特定function
    #     self.write(':FUNC:MODE USER')
    #     #选择特定channel
    #     self.write(':INST:SEL %d' % ch)
    #     #定义特定的segment
    #     self.write(':TRAC:DEF %d,%d' % (trac, pointslen))
    #     #选择特定的segment
    #     self.write(':TRAC:SEL %d' % trac)
    #     #选择模式为SINGLE，（包括DUPLicate，SINGle等，详见manual）
    #     self.write(':TRAC:MODE SING')
    #     #写入波形数据
    #     message = ':TRAC:DATA'  # % (len(str(pointslen2)),pointslen2)
    #     points = points.clip(-1, 1)
    #     values = np.zeros(pointslen).astype(np.uint16)
    #     #乘积选用8191是为了防止最终值大于16383
    #     values = (points * 8191).astype(np.uint16) + 8192  #.astype(np.uint16)
    #     byte = np.zeros(pointslen2).astype(np.uint8)
    #     #将原先的两比特数据点，分割为高低两个比特
    #     byte[0:pointslen2:2] = (values & 0b11111111).astype(np.uint8)
    #     byte[1:pointslen2:2] = ((values & 0b11111100000000) >> 8).astype(
    #         np.uint8)
    #     #write_binary_value中的message参数不要包括#42048的信息，因为pyvisa可以自动算出结果。详见pyvisa中util.py内的to_binary_block
    #     #wx2184选用little_endian。这表示程序按照我给的顺序将二进制包写进去
    #     self.write_binary_values(message,
    #                              byte,
    #                              datatype='B',
    #                              is_big_endian=False,
    #                              termination=None,
    #                              encoding=None)
    #     # self.write('enable' )