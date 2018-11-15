# -*- coding: utf-8 -*-
import sys
sys.path.append('C:\Program Files (x86)\Keysight\SD1\Libraries\Python')
import keysightSD1

import numpy as np
from qulab import BaseDriver, QOption, QReal, QList

class Driver(BaseDriver):
    support_models = ['M3202A', ]
    quants = []

    def __init__(self, **kw):
        BaseDriver.__init__(self, **kw)
        self.PRODUCT=kw['PRODUCT']
        self.CHASSIS=kw['CHASSIS']
        self.SLOT=kw['SLOT']
