# -*- coding: utf-8 -*-
import sys
sys.path.append(r'C:\Program Files (x86)\Keysight\SD1\Libraries\Python')
import keysightSD1

import numpy as np
import logging
from qulab.Driver import BaseDriver, QOption, QReal, QList, QInteger

log = logging.getLogger(__name__)
# log.addHandler(logging.NullHandler())

class Driver(BaseDriver):
    support_models = ['M3202A', ]

    quants = [
        QReal('Amplitude', value=1, unit='V', ch=1),
        #DC WaveShape
        QReal('Offset', value=0, unit='V', ch=1),
        #Function Generators(FGs) mode
        QReal('Frequency', unit='Hz', ch=1),
        QReal('Phase', value=0, unit='deg', ch=1),

        QOption('WaveShape', ch=1, value='HIZ',
            options = [('HIZ',       -1),
                       ('NoSignal',   0),
                       ('Sin',        1),
                       ('Triangular', 2),
                       ('Square',     4),
                       ('DC',         5),
                       ('AWG',        6),
                       ('PartnerCH',  8)]),
        #clock
        QReal('clockFrequency', unit='Hz'),
        QReal('clockSyncFrequency', unit='Hz'),
        # 板卡向外输出的时钟，默认状态关闭
        QOption('clockIO', value='OFF', options = [('OFF', 0), ('ON',  1)]),
        QOption('triggerIO', value='SyncIN',
                            options = [('noSyncOUT', (0,0)),
                                       ('SyncOUT',   (0,1)),
                                       ('noSyncIN',  (1,0)),
                                       ('SyncIN',    (1,1))]),

        QOption('triggerMode', value='ExternalCycle', ch=1,
                             options = [('Auto',         0),
                                        ('SWtri',        1),
                                        ('SWtriCycle',   5),
                                        ('External',     2),
                                        ('ExternalCycle',6)]),
        QOption('triExtSource', value='EXTERN', ch=1,
                             options = [('EXTERN', 0),
                                        ('PXI0', 4000),
                                        ('PXI1', 4001),
                                        ('PXI2', 4002),
                                        ('PXI3', 4003),
                                        ('PXI4', 4004),
                                        ('PXI5', 4005),
                                        ('PXI6', 4006),
                                        ('PXI7', 4007)]),
        QOption('triggerBehavior', value='RISE', ch=1,
                             options = [('NONE', 0),
                                        ('HIGH', 1),
                                        ('LOW',  2),
                                        ('RISE', 3),
                                        ('FALL', 4)]),
        # Defines the delay between the trigger and the waveform launch in tens of ns
        QInteger('startDelay', value=0, unit='ns', ch=1, ),
        # Number of times the waveform is repeated once launched (negative means infinite)
        QInteger('cycles', value=0, ch=1,),
        # Waveform prescaler value, to reduce the effective sampling rate
        QInteger('prescaler', value=0, ch=1,),

        QOption('Output', ch=1, value='Close', options = [('Stop', 0),  ('Run', 1),
                                                          ('Pause', 2), ('Resume', 3),
                                                          ('Close', -1)]),
        QList('WList', value=[]),
        QList('SList', value=[], ch=1),
    ]
    #CHs : 仪器通道
    CHs=[1,2,3,4]

    def __init__(self, addr, **kw):
        super().__init__(self, addr, **kw)

    def performOpen(self):
        #SD_AOU module
        dict_parse=self._parse_addr(self.addr)
        CHASSIS=dict_parse.get('CHASSIS') #default 1
        SLOT=dict_parse.get('SLOT')
        self.handle = keysightSD1.SD_AOU()
        self.model = self.handle.getProductNameBySlot(CHASSIS,SLOT)
        moduleID = self.handle.openWithSlot(self.model, CHASSIS, SLOT)
        if moduleID < 0:
        	print("Module open error:", moduleID)
        except Exception:
            log.exception(Exception)

    def _parse_addr(self,addr):
        re_addr = re.compile(
            r'^(PXI)[0-9]?::CHASSIS([0-9]*)::SLOT([0-9]*)::FUNC([0-9]*)::INSTR$')
        m = re_addr.search(addr)
        if m is None:
            raise Error('Address error!')
        CHASSIS = int(pxi.group(2))
        SLOT = int(pxi.group(3))
        return dict(CHASSIS=CHASSIS,SLOT=SLOT)

    def performClose(self):
        """Perform the close instrument connection operation"""
        # refer labber driver keysight_pxi_awg.py
        # do not check for error if close was called with an error
        try:
            self.setValue('clockIO','OFF')
            # clear old waveforms and stop awg
            self.waveformFlush()
            for ch in self.CHs:
                self.closeCh(ch)
            # close instrument
            # self.handle.close()
        except Exception:
            # never return error here
            pass

    def closeCh(self,ch=1):
        self.handle.AWGstop(ch)
        self.handle.AWGflush(ch)
        self.config['SList'][ch]['value']=[]
        self.handle.channelWaveShape(ch, -1)
        self.config['WaveShape'][ch]['value']='HIZ'
        self.config['Output'][ch]['value']='Close'

    def performSetValue(self, quant, value, **kw):
        ch = kw.get('ch',1)
        if quant.name == 'Amplitude':
            self.handle.channelAmplitude(ch, value)
        elif quant.name == 'Offset':
            self.handle.channelOffset(ch, value)
        elif quant.name == 'Frequency':
            self.handle.channelFrequency(ch, value)
        elif quant.name == 'Phase':
            self.phaseReset(ch)
            self.handle.channelPhase(ch, value)
        elif quant.name == 'WaveShape':
            options=dict(quant.options)
            self.handle.channelWaveShape(ch, options[value])
        elif quant.name == 'clockFrequency':
            mode=kw.get('mode',1)
            self.handle.clockSetFrequency(value,mode)
        elif quant.name == 'clockIO':
            options=dict(quant.options)
            self.handle.clockIOconfig(options[value])
        elif quant.name == 'triggerIO':
            options=dict(quant.options)
            self.handle.triggerIOconfigV5(*options[value])
        elif quant.name == 'Output':
            if value=='Stop':
                self.handle.AWGstop(ch)
            elif value=='Run':
                self.handle.AWGstart(ch)
            elif value=='Pause':
                self.handle.AWGpause(ch)
            elif value=='Resume':
                self.handle.AWGresume(ch)
            elif value=='Close':
                self.closeCh(ch)
        elif quant.name == 'clockSyncFrequency':
            raise Error("clockSyncFrequency can't be set")


    def performGetValue(self, quant, **kw):
        if quant.name == 'clockFrequency':
            return self.handle.clockGetFrequency() 
        elif quant.name == 'clockSyncFrequency':
            return self.handle.clockGetSyncFrequency()
        else:
            return super().performGetValue(quant, **kw)

    def phaseReset(self,ch=1):
        self.handle.channelPhaseReset(ch)

    def clockResetPhase(self):
        # self.handle.clockResetPhase(triggerBehavior, triggerSource, skew = 0.0)
        pass

    def newWaveform(self, file_arrayA, arrayB=None, waveformType=0):
        '''Memory usage: Waveforms created with New are stored in the PC RAM,
        not in the module onboard RAM. Therefore, the limitation in the number
        of waveforms and their sizes is given by the amount of PC RAM.'''
        # waveformType 0: Analog 16Bits, Analog normalized waveforms (-1..1) defined with doubles
        # please refer AWG Waveform types about others
        wave = keysightSD1.SD_Wave()
        if isinstance(file_arrayA, str):
            wave.newFromFile(file_arrayA)
            return wave
        else:
            # 5: DigitalType, Digital waveforms defined with integers
            if waveformType==5:
                wave.newFromArrayInteger(waveformType, file_arrayA, arrayB)
            else:
                wave.newFromArrayDouble(waveformType, file_arrayA, arrayB)
            return wave

    def waveformLoad(self, waveform, num, paddingMode = 0):
        '''num: waveform_num, 在板上内存的波形编号'''
        if num in self.config['WList']['global']['value']:
            self.handle.waveformReLoad(waveform, num, paddingMode)
        else:
            # This function replaces a waveform located in the module onboard RAM.
            # The size of the newwaveform must be smaller than or equal to the existing waveform.
            self.handle.waveformLoad(waveform, num, paddingMode)
            self.config['WList']['global']['value'].append(num)

    # def waveformReLoad(self, waveform, num, paddingMode = 0):
    #     '''This function replaces a waveform located in the module onboard RAM.
    #     The size of the newwaveform must be smaller than or equal to the existing waveform.'''
    #     self.handle.waveformReLoad(waveform, num, paddingMode)

    def waveformFlush(self):
        '''This function deletes all the waveforms from the module onboard RAM
        and flushes all the AWG queues'''
        self.handle.waveformFlush()
        self.config['WList']['global']['value']=[]
        for ch in self.CHs:
            self.config['SList'][ch]['value']=[]

    def AWGflush(self,ch=1):
        '''This function empties the queue of the selected Arbitrary Waveform Generator,
        Waveforms are not removed from the module onboard RAM.'''
        self.handle.AWGflush(ch)
        self.config['SList'][ch]['value']=[]

    def _getParams(self, ch):
        triggerModeIndex = self.getValue('triggerMode',ch=ch)
        triggerModeOptions=self.quantities['triggerMode'].options
        triggerMode = dict(triggerModeOptions)[triggerModeIndex]

        if triggerModeIndex in ['External','ExternalCycle']:

            triExtSourceIndex = self.getValue('triExtSource',ch=ch)
            triExtSourceOptions=self.quantities['triExtSource'].options
            triExtSource = dict(triExtSourceOptions)[triExtSourceIndex]
            if triExtSourceIndex in ['EXTERN']:
                # 若未设置过，则从config读取默认配置；若已设置，则结果不变
                triggerIO = self.getValue('triggerIO')
                self.setValue('triggerIO', triggerIO)

            triggerBehaviorIndex = self.getValue('triggerBehavior',ch=ch)
            triggerBehaviorOptions=self.quantities['triggerBehavior'].options
            triggerBehavior = dict(triggerBehaviorOptions)[triggerBehaviorIndex]

            self.handle.AWGtriggerExternalConfig(ch, triExtSource, triggerBehavior)

        startDelay = self.getValue('startDelay',ch=ch)
        cycles = self.getValue('cycles',ch=ch)
        prescaler = self.getValue('prescaler',ch=ch)

        return triggerMode, startDelay, cycles, prescaler

    def AWGqueueWaveform(self, ch=1, waveform_num=0):
        self.setValue('WaveShape', 'AWG', ch=ch)
        Amplitude=self.getValue('Amplitude',ch=ch)
        self.setValue('Amplitude', Amplitude, ch=ch)

        triggerMode, startDelay, cycles, prescaler=self._getParams(ch)

        self.handle.AWGqueueWaveform(ch, waveform_num, triggerMode, startDelay, cycles, prescaler)
        self.config['SList'][ch]['value'].append(waveform_num)

    def AWGrun(self, file_arrayA, arrayB=None, ch=1, waveformType=0, paddingMode = 0):
        '''从文件或序列快速产生波形'''
        self.setValue('WaveShape', 'AWG', ch=ch)
        Amplitude=self.getValue('Amplitude',ch=ch)
        self.setValue('Amplitude', Amplitude, ch=ch)

        triggerMode, startDelay, cycles, prescaler=self._getParams(ch)

        if isinstance(file_arrayA, str):
            # AWGFromFile 有bug
            self.handle.AWGFromFile(ch, file_arrayA, triggerMode, startDelay, cycles, prescaler, paddingMode)
        else:
            self.handle.AWGfromArray(ch, triggerMode, startDelay, cycles, prescaler, waveformType, file_arrayA, arrayB, paddingMode)
        self.config['Output'][ch]['value']='Run'
