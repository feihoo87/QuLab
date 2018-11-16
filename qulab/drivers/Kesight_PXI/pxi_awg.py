# -*- coding: utf-8 -*-
import sys
try:
    sys.path.append('C:\Program Files (x86)\Keysight\SD1\Libraries\Python')
import keysightSD1

import numpy as np
from qulab import BaseDriver, QOption, QReal, QList

class Driver(BaseDriver):
    support_models = ['M3202A', ]
    quants = [
        QReal('Amplitude', unit='V', ch=0),
        QReal('Offset', unit='V', ch=0),
        QReal('Frequency', unit='Hz', ch=0),
        QReal('Phase', unit='deg', ch=0),
        QOption('WaveShape', ch=0,
            options = [('HIZ',       -1),
                       ('NoSignal',   0),
                       ('Sin',        1),
                       ('Triangular', 2),
                       ('Square',     4),
                       ('DC',         5),
                       ('AWG',        6),
                       ('PartnerCH',  8)]),
        QReal('clockFrequency', unit='Hz'),
        QReal('clockSyncFrequency', unit='Hz'),
    ]

    def __init__(self, **kw):
        BaseDriver.__init__(self, **kw)
        self.chassis=kw['CHASSIS']
        self.slot=kw['SLOT']

    def performOpen(self):
        #SD_AOU module
        self.AWG = keysightSD1.SD_AOU()
        self.product = self.AWG.getProductNameBySlot(self.chassis,self.slot)
        moduleID = self.AWG.openWithSlot(self.product, self.chassis, self.slot)
        if moduleID < 0:
        	print("Module open error:", moduleID)

    def performClose(self):
        """Perform the close instrument connection operation"""
        # from labber driver keysight_pxi_awg.py
        # do not check for error if close was called with an error
        try:
            # clear old waveforms and stop awg
            self.AWG.waveformFlush()
            for ch in range(4):
                self.AWG.AWGstop(ch)
                self.AWG.AWGflush(ch)
                self.AWG.channelWaveShape(ch, -1)
            # close instrument
            self.AWG.close()
        except Exception:
            # never return error here
            pass

    def closeCh(self,ch=0):
        self.AWG.AWGstop(ch)
        self.AWG.AWGflush(ch)
        self.AWG.channelWaveShape(ch, -1)

    def performSetValue(self, quant, value, **kw):
        if quant.name == 'Amplitude':
            ch=kw.get('ch',quant.ch)
            self.AWG.channelAmplitude(ch, value)
        elif quant.name == 'Offset':
            ch=kw.get('ch',quant.ch)
            self.AWG.channelOffset(ch, value)
        elif quant.name == 'Frequency':
            ch=kw.get('ch',quant.ch)
            self.AWG.channelFrequency(ch, value)
        elif quant.name == 'Phase':
            ch=kw.get('ch',quant.ch)
            self.phaseReset(ch)
            self.AWG.channelPhase(ch, value)
        elif quant.name == 'WaveShape':
            ch=kw.get('ch',quant.ch)
            options=dict(self.options)
            self.AWG.channelWaveShape(ch, options[value])
        elif quant.name == 'clockFrequency':
            mode=kw.get('mode',1)
            self.AWG.clockSetFrequency(value,mode)

    def performGetValue(self, quant, **kw):
        if quant.name == 'clockFrequency':
            return self.AWG.clockGetFrequency()
        elif quant.name == 'clockSyncFrequency':
            return self.AWG.clockGetSyncFrequency()

    def phaseReset(self,ch=0):
        self.AWG.channelPhaseReset(ch)

    def clockResetPhase(self):
        # self.AWG.clockResetPhase(triggerBehavior, triggerSource, skew = 0.0)
        pass

    def newWaveform(self,file_array=None):
        if isinstance(file_array, str):
            wave = keysightSD1.SD_Wave()
            wave.newFromFile(file_array)
            return wave
        elif isinstance(file_array, (list,tuple))






    # def AWG_file(self,wave_file,ch=0,wave_id=0):
    #     '''从文件载入波形，并输出
    #         wave_file: 波形文件'''
    #     # create, open from file, load to module RAM and queue for execution
    #     wave = keysightSD1.SD_Wave()
    #     wave.newFromFile(wave_file)
    #     module = self.AWG
    #     module.waveformLoad(wave, 0)
    # 	module.AWGqueueWaveform(ch, wave_id, 0, 0, 0, 0)
    #     error = module.AWGstart(0)
    #     if error < 0:
    # 		print("AWG from file error:", error)
    #
    # def AWG_array(self,waveform_data_list,ch=0):
    #     # WAVEFORM FROM ARRAY/LIST
    # 	# This function is equivalent to create a waveform with new,
    # 	# and then to call waveformLoad, AWGqueueWaveform and AWGstart
    #     module = self.AWG
    # 	error = module.AWGfromArray(ch, 0, 0, 0, 0, 0, waveform_data_list)
    #     if error < 0:
    # 		print("AWG from array error:", error)
