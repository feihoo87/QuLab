# -*- coding: utf-8 -*-
import numpy as np

from qulab import BaseDriver, QInteger, QOption, QReal, QString, QVector

from .PG_DC_api import Voltage


class Driver(BaseDriver):
    support_models = ['PG_DC']
    quants = [
        QReal('Offset', value=0, ch=0),
            ]

    def __init__(self, **kw):
        BaseDriver.__init__(self, **kw)
        self.ip=kw['IP']
        self.model = 'PG_DC'

    def performOpen(self):
        self.handle = Voltage(self.ip)

    def performSetValue(self, quant, value, ch=0, **kw):
        if quant.name == 'Offset':
            self.handle.setVoltage(value,ch=ch)
