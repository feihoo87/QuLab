import numpy as np
import logging
log = logging.getLogger(__name__)

from qulab.Driver import visaDriver, QOption, QReal


class Driver(visaDriver):
    __log__=log
    error_command = '*ESR?'
    support_models = ['AFG3102']

    CHs=[1,2]
    quants = [
        QOption('Output',
                ch=1,
                set_cmd='OUTP%(ch)d %(option)s',
                get_cmd='OUTP%(ch)d?',
                options=[('OFF', 'OFF'), ('ON', 'ON')]),  # must set chanel
        QOption('Function',
                ch=1,
                set_cmd='SOUR%(ch)d:FUNC %(option)s',
                get_cmd='SOUR%(ch)d:FUNC?',
                options=[('Sin', 'SIN'), ('Square', 'SQU'), ('Pulse', 'PULS'),
                         ('Ramp', 'RAMP'), ('PRNoise', 'PRN'), ('DC', 'DC'),
                         ('SINC', 'SINC'), ('Gaussian', 'GAUS'),
                         ('Lorentz', 'LOR'), ('Erise', 'ERIS'),
                         ('Edecay', 'EDEC'), ('Haversine', 'HAV'),
                         ('User', 'USER'), ('User2', 'USER2')]),
        QReal('Frequency',
              unit='Hz',
              ch=1,
              set_cmd='SOUR%(ch)d:FREQ %(value)e%(unit)s',
              get_cmd='SOUR%(ch)d:FREQ?'),
        QReal('Phase',
              unit='rad',
              ch=1,
              set_cmd='SOUR%(ch)d:PHAS %(value)f%(unit)s',
              get_cmd='SOUR%(ch)d:PHAS?'),
        QReal('Pulse Delay',
              unit='s',
              ch=1,
              set_cmd='SOUR%(ch)d:PULS:DEL %(value).9e%(unit)s',
              get_cmd='SOUR%(ch)d:PULS:DEL?'),
        QReal('Pulse Period',
              unit='s',
              ch=1,
              set_cmd='SOUR%(ch)d:PULS:PER %(value).9e%(unit)s',
              get_cmd='SOUR%(ch)d:PULS:PER?'),
        QReal('Pulse Width',
              unit='s',
              ch=1,
              set_cmd='SOUR%(ch)d:PULS:WIDT %(value).9e%(unit)s',
              get_cmd='SOUR%(ch)d:PULS:WIDT?'),
        #Burst Mode
        QReal('Burst Tdelay',
              unit='s',
              ch=1,
              set_cmd='SOUR%(ch)d:BURS:TDEL %(value).9e%(unit)s',
              get_cmd='SOUR%(ch)d:BURS:TDEL?'),
        QReal('Burst Ncycles',
              ch=1,
              set_cmd='SOUR%(ch)d:BURS:NCYC %(value)d',
              get_cmd='SOUR%(ch)d:BURS:NCYC?'),
        ##
        QReal('Frequency',
              unit='Hz',
              ch=1,
              set_cmd='SOUR%(ch)d:FREQ %(value)e%(unit)s',
              get_cmd='SOUR%(ch)d:FREQ?'),
        QReal('Phase',
              unit='DEG',
              ch=1,
              set_cmd='SOUR%(ch)d:PHAS %(value)f%(unit)s',
              get_cmd='SOUR%(ch)d:PHAS?'),
        QReal('High Level',
              unit='V',
              ch=1,
              set_cmd='SOUR%(ch)d:VOLT:HIGH %(value)f%(unit)s',
              get_cmd='SOUR%(ch)d:VOLT:HIGH?'),
        QReal('Low Level',
              unit='V',
              ch=1,
              set_cmd='SOUR%(ch)d:VOLT:LOW %(value)f%(unit)s',
              get_cmd='SOUR%(ch)d:VOLT:LOW?'),
        QReal('Offset',
              unit='V',
              ch=1,
              set_cmd='SOUR%(ch)d:VOLT:OFFS %(value)f%(unit)s',
              get_cmd='SOUR%(ch)d:VOLT:OFFS?'),
        QReal('Amplitude',
              unit='VPP',
              ch=1,
              set_cmd='SOUR%(ch)d:VOLT:AMPL %(value)f%(unit)s',
              get_cmd='SOUR%(ch)d:VOLT:AMPL?'),
    ]

    def reset(self, delay1=0, delay2=0):
        #init
        self.write('*CLS')
        self.write('*RST')
        #set external clock;external source;burst mode&cycle=1&trigdelay=0
        self.write('SOURce:ROSCillator:SOURce EXT')
        self.write('TRIGger:SEQuence:SOURce EXTernal')
        self.write('SOURce1:BURSt:STATe ON')
        self.write('SOURce1:BURSt:NCYCles 1')
        self.write('SOURce1:BURSt:MODE TRIGgered')
        self.write('SOURce1:BURSt:DELay %fus' % delay1)
        self.write('SOURce2:BURSt:STATe ON')
        self.write('SOURce2:BURSt:NCYCles 1')
        self.write('SOURce2:BURSt:MODE TRIGgered')
        self.write('SOURce2:BURSt:TDELay %fns' % delay2)

    #在创建好的波形文件中，写入或者更新具体波形
    def upwave(self, points, ch=1, T0=100):
        pointslen = len(points)
        pointslen2 = 2 * pointslen
        #写入波形数据
        self.write('DATA:DEFine EMEMory,%d' % pointslen)
        self.write('DATA:POINts EMEMory, %d' % pointslen)
        message = ':DATA:DATA EMEMory,'  # % (len(str(pointslen2)),pointslen2)
        points = points.clip(-1, 1)
        values = np.zeros(pointslen).astype(np.uint16)
        #乘积选用8191是为了防止最终值大于16383
        values = (points * 8191).astype(np.uint16) + 8192  #.astype(np.uint16)
        byte = np.zeros(pointslen2).astype(np.uint8)
        #将原先的两比特数据点，分割为高低两个比特
        byte[1:pointslen2:2] = (values & 0b11111111).astype(np.uint8)
        byte[0:pointslen2:2] = ((values & 0b11111100000000) >> 8).astype(
            np.uint8)
        #write_binary_value中的message参数不要包括#42048的信息，因为pyvisa可以自动算出结果。详见pyvisa中util.py内的to_binary_block
        #AFG3102选用big_endian。这表示程序按照我给的顺序将二进制包写进去
        self.write_binary_values(message,
                                 byte,
                                 datatype='B',
                                 is_big_endian=False,
                                 termination=None,
                                 encoding=None)
        # self.write('enable' )
        self.write('TRAC:COPY USER%d,EMEM' % ch)
        self.write('SOURce%d:FUNCTION USER%d' % (ch, ch))
        #set frequency:because the wave total length is set by this parameter,typical for 1Mhz means the wave length is set to 1us!!
        self.write('SOURce%d:FREQuency:FIXed %fkHz' % (ch, 1e3 / T0))
        self.write('OUTPut%d:STATe ON' % ch)
