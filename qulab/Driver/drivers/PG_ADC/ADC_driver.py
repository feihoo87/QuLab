# -*- coding: utf-8 -*-
import numpy as np
from qulab.Driver import BaseDriver, QInteger, QOption, QReal, QString, QVector
from . import TimeDomainPlotCore as ad_core

import logging
log = logging.getLogger(__name__)

class Driver(BaseDriver):

    __log__=log
    
    support_models = ['PG_ADC']
    # quants = [
    #     # QReal('Offset', value=0, ch=0),
    #         ]

    def __init__(self, addr, **kw):
        '''addr: IP'''
        super().__init__(self, addr, **kw)
        self.model = 'PG_ADC'

    def performOpen(self):
        ad_core._gUDPSocketClient = ad_core.UDPSocketClient(ip=self.addr)
        ad_core.Initialize()
        ad_core.setTriggerType(1) # 外部触发
        self.handle = ad_core

    # def performSetValue(self, quant, value, ch=0, **kw):
    #     if quant.name == 'Offset':
    #         self.handle.setVoltage(value,ch=ch)

    def getData(self, length, repeats):
        self.handle.setRecordLength(recordLength=length)
        self.handle.setFrameNumber(frameNum=repeats)
        self.handle.startCapture()
        data = self.handle.getData()
        return data
