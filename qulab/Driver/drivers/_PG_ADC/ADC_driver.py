# -*- coding: utf-8 -*-
import numpy as np
from qulab import BaseDriver, QInteger, QOption, QReal, QString, QVector
from . import TimeDomainPlotCore as ad_core


class Driver(BaseDriver):
    support_models = ['PG_ADC']
    # quants = [
    #     # QReal('Offset', value=0, ch=0),
    #         ]

    def __init__(self, **kw):
        BaseDriver.__init__(self, **kw)
        self.ip=kw['IP']
        self.model = 'PG_ADC'

    def performOpen(self):
        ad_core._gUDPSocketClient = ad_core.UDPSocketClient(ip=self.ip)
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
