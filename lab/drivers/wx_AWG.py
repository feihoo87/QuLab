# -*- coding: utf-8 -*-
import numpy as np
from lab.device import BaseDriver, QInteger, QOption, QReal, QString, QVector


class Driver(BaseDriver):
    surport_models = ['WX1284', 'WX2184']

    quants = [
        QReal('Sample Rate', unit='S/s',
          set_cmd=':FREQ:RAST %(value)g',
          get_cmd=':FREQ:RAST?'),
    ]

    def performOpen(self):
        pass

    def performSetValue(self, quant, value, **kw):
        pass

    def performGetValue(self, quant, **kw):
        pass
