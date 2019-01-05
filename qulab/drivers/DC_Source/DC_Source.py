# -*- coding: utf-8 -*-
import numpy as np

from qulab import BaseDriver, QInteger, QOption, QReal, QString, QVector

from .Highfine_DCsource import Voltage


class Driver(BaseDriver):
    support_models = ['Highfine_DCsource']
    quants = [
        QReal('Offset', value=0, ch=0),
            ]

    def __init__(self, **kw):
        BaseDriver.__init__(self, **kw)
        self.ip=kw['IP']

    def performOpen(self):
        self.handle = Voltage(self.ip)

    def performSetValue(self, quant, value, ch=0, **kw):
        if quant.name == 'Offset':
            self.handle.setVoltage(value,ch=ch)
