# -*- coding: utf-8 -*-
import sys
sys.path.append(r'C:\Program Files (x86)\Keysight\SD1\Libraries\Python')
import keysightSD1

import numpy as np
import yaml
import logging
from qulab import BaseDriver, QOption, QReal, QList, QInteger
from qulab.config import caches_dir

log = logging.getLogger(__name__)
# log.addHandler(logging.NullHandler())

class Driver(BaseDriver):
    support_models = ['M3202A', ]

    quants = [
        QReal('Amplitude', value=1, unit='V', ch=0),
        #DC WaveShape
        QReal('Offset', value=0, unit='V', ch=0),
        #Function Generators(FGs) mode
        QReal('Frequency', unit='Hz', ch=0),
        QReal('Phase', value=0, unit='deg', ch=0),

        QOption('WaveShape', ch=0, value='HIZ',
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

        QOption('triggerMode', value='ExternalCycle', ch=0,
                             options = [('Auto',         0),
                                        ('SWtri',        1),
                                        ('SWtriCycle',   5),
                                        ('External',     2),
                                        ('ExternalCycle',6)]),
        QOption('triExtSource', value='EXTERN', ch=0,
                             options = [('EXTERN', 0),
                                        ('PXI0', 4000),
                                        ('PXI1', 4001),
                                        ('PXI2', 4002),
                                        ('PXI3', 4003),
                                        ('PXI4', 4004),
                                        ('PXI5', 4005),
                                        ('PXI6', 4006),
                                        ('PXI7', 4007)]),
        QOption('triggerBehavior', value='RISE', ch=0,
                             options = [('NONE', 0),
                                        ('HIGH', 1),
                                        ('LOW',  2),
                                        ('RISE', 3),
                                        ('FALL', 4)]),
        # Defines the delay between the trigger and the waveform launch in tens of ns
        QInteger('startDelay', value=0, unit='ns', ch=0, ),
        # Number of times the waveform is repeated once launched (negative means infinite)
        QInteger('cycles', value=0, ch=0,),
        # Waveform prescaler value, to reduce the effective sampling rate
        QInteger('prescaler', value=0, ch=0,),

        QOption('Output', ch=0, value='Close', options = [('Stop', 0),  ('Run', 1),
                                                          ('Pause', 2), ('Resume', 3),
                                                          ('Close', -1)]),
        QList('WList', value=[]),
        QList('SList', value=[], ch=0),
    ]
    #CHs : 仪器通道
    CHs=[0,1,2,3]
    # config : 用来存储参数配置，防止由于多通道引起的混乱
    config={}

    def __init__(self, **kw):
        BaseDriver.__init__(self, **kw)
        self.chassis=kw['CHASSIS']
        self.slot=kw['SLOT']

    def newcfg(self):
        self.config={}
        for q in self.quants:
            _cfg={q.name:{}}
            if q.ch is not None:
                for i in self.CHs:
                    _cfg[q.name].update({i:{'value':q.value, 'unit':q.unit}})
            else:
                _cfg[q.name].update({0:{'value':q.value, 'unit':q.unit}})
            self.config.update(_cfg)
        log.info('new config!')

    def loadcfg(self, file=None):
        if file == None:
            file = self.caches_file
        with open(file, 'r', encoding='utf-8') as f:
            self.config=yaml.load(f)
        log.info('load config: %s',file)

    def savecfg(self, file=None):
        if file == None:
            file = self.caches_file
        with open(file, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f)
        log.info('save config: %s',file)


    def performOpen(self):
        #SD_AOU module
        self.AWG = keysightSD1.SD_AOU()
        self.model = self.AWG.getProductNameBySlot(self.chassis,self.slot)
        moduleID = self.AWG.openWithSlot(self.model, self.chassis, self.slot)
        if moduleID < 0:
        	print("Module open error:", moduleID)
        self.caches_file = caches_dir() / (self.model+'_config_caches.yaml')
        try:
            self.loadcfg()
        except Exception:
            log.exception(Exception)
            self.newcfg()
            self.savecfg()

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
            # self.AWG.close()
            self.savecfg()
        except Exception:
            # never return error here
            pass

    def closeCh(self,ch=0):
        self.AWG.AWGstop(ch)
        self.AWG.AWGflush(ch)
        self.config['SList'][ch]['value']=[]
        self.AWG.channelWaveShape(ch, -1)
        self.config['WaveShape'][ch]['value']='HIZ'
        self.config['Output'][ch]['value']='Close'

    def performSetValue(self, quant, value, ch=0, **kw):
        _cfg={}
        if quant.name == 'Amplitude':
            self.AWG.channelAmplitude(ch, value)
        elif quant.name == 'Offset':
            self.AWG.channelOffset(ch, value)
        elif quant.name == 'Frequency':
            self.AWG.channelFrequency(ch, value)
        elif quant.name == 'Phase':
            self.phaseReset(ch)
            self.AWG.channelPhase(ch, value)
        elif quant.name == 'WaveShape':
            options=dict(quant.options)
            self.AWG.channelWaveShape(ch, options[value])
        elif quant.name == 'clockFrequency':
            mode=kw.get('mode',1)
            self.AWG.clockSetFrequency(value,mode)
            ch=0
        elif quant.name == 'clockIO':
            options=dict(quant.options)
            self.AWG.clockIOconfig(options[value])
            ch=0
        elif quant.name == 'triggerIO':
            options=dict(quant.options)
            self.AWG.triggerIOconfigV5(*options[value])
            ch=0
        elif quant.name == 'Output':
            if value=='Stop':
                self.AWG.AWGstop(ch)
            elif value=='Run':
                self.AWG.AWGstart(ch)
            elif value=='Pause':
                self.AWG.AWGpause(ch)
            elif value=='Resume':
                self.AWG.AWGresume(ch)
            elif value=='Close':
                self.closeCh(ch)
        elif quant.name == 'clockSyncFrequency':
            print("clockSyncFrequency can't be set")
            return
        _cfg['value']=value
        self.config[quant.name][ch].update(_cfg)


    def performGetValue(self, quant, ch=0, **kw):
        _cfg={}
        if quant.name == 'clockFrequency':
            value=self.AWG.clockGetFrequency()
            ch=0
            _cfg['value']=value
        elif quant.name == 'clockSyncFrequency':
            value=self.AWG.clockGetSyncFrequency()
            ch=0
            _cfg['value']=value
        elif quant.name in ['clockIO','triggerIO']:
            ch=0
        self.config[quant.name][ch].update(_cfg)
        return self.config[quant.name][ch]['value']

    def phaseReset(self,ch=0):
        self.AWG.channelPhaseReset(ch)
        _cfg={'value':0}
        self.config['Phase'][ch].update(_cfg)

    def clockResetPhase(self):
        # self.AWG.clockResetPhase(triggerBehavior, triggerSource, skew = 0.0)
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
        if num in self.config['WList'][0]['value']:
            self.AWG.waveformReLoad(waveform, num, paddingMode)
        else:
            # This function replaces a waveform located in the module onboard RAM.
            # The size of the newwaveform must be smaller than or equal to the existing waveform.
            self.AWG.waveformLoad(waveform, num, paddingMode)
            self.config['WList'][0]['value'].append(num)

    # def waveformReLoad(self, waveform, num, paddingMode = 0):
    #     '''This function replaces a waveform located in the module onboard RAM.
    #     The size of the newwaveform must be smaller than or equal to the existing waveform.'''
    #     self.AWG.waveformReLoad(waveform, num, paddingMode)

    def waveformFlush(self):
        '''This function deletes all the waveforms from the module onboard RAM
        and flushes all the AWG queues'''
        self.AWG.waveformFlush()
        self.config['WList'][0]['value']=[]
        self.config['SList'][0]['value']=[]

    def AWGflush(self,ch=0):
        '''This function empties the queue of the selected Arbitrary Waveform Generator,
        Waveforms are not removed from the module onboard RAM.'''
        self.AWG.AWGflush(ch)
        self.config['SList'][0]['value']=[]

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

            self.AWG.AWGtriggerExternalConfig(ch, triExtSource, triggerBehavior)

        startDelay = self.getValue('startDelay',ch=ch)
        cycles = self.getValue('cycles',ch=ch)
        prescaler = self.getValue('prescaler',ch=ch)

        return triggerMode, startDelay, cycles, prescaler

    def AWGqueueWaveform(self, ch=0, waveform_num=0):
        self.setValue('WaveShape', 'AWG', ch=ch)
        Amplitude=self.getValue('Amplitude',ch=ch)
        self.setValue('Amplitude', Amplitude, ch=ch)

        triggerMode, startDelay, cycles, prescaler=self._getParams(ch)

        self.AWG.AWGqueueWaveform(ch, waveform_num, triggerMode, startDelay, cycles, prescaler)
        self.config['SList'][ch]['value'].append(waveform_num)

    def AWGrun(self, file_arrayA, arrayB=None, ch=0, waveformType=0, paddingMode = 0):
        '''从文件或序列快速产生波形'''
        self.setValue('WaveShape', 'AWG', ch=ch)
        Amplitude=self.getValue('Amplitude',ch=ch)
        self.setValue('Amplitude', Amplitude, ch=ch)

        triggerMode, startDelay, cycles, prescaler=self._getParams(ch)

        if isinstance(file_arrayA, str):
            # AWGFromFile 有bug
            self.AWG.AWGFromFile(ch, file_arrayA, triggerMode, startDelay, cycles, prescaler, paddingMode)
        else:
            self.AWG.AWGfromArray(ch, triggerMode, startDelay, cycles, prescaler, waveformType, file_arrayA, arrayB, paddingMode)
        self.config['Output'][ch]['value']='Run'
