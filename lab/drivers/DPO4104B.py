# -*- coding: utf-8 -*-
import numpy as np

from lab.device import BaseDriver
from lab.device import QReal, QOption, QInteger, QString, QVector

class Driver(BaseDriver):
    surport_models = ['DPO4104B']

    quants = [
        QReal('X Scale', set_cmd='HOR:SCA %(value)e', get_cmd='HOR:SCA?'),
        QInteger('Bytes per Point', set_cmd='WFMI:BYT_N?', get_cmd='WFMI:BYT_N?'),
        QReal('X Step', set_cmd=':WFMI:XIN %(value)e', get_cmd=':WFMI:XIN?'),
        QReal('X Zero', set_cmd=':WFMI:XZER %(value)e', get_cmd=':WFMI:XZER?'),
        QReal('Y Scale', set_cmd=':CH%(ch)d:SCA %(value)e', get_cmd=':CH%(ch)d:SCA?'),
        QReal('Y Position', set_cmd=':CH%(ch)d:POS %(value)e', get_cmd=':CH%(ch)d:POS?'),
        QReal('Y Mult', set_cmd=':WFMI:YMU %(value)e', get_cmd=':WFMI:YMU?'),
        QReal('Y Offset', set_cmd=':WFMI:YOF %(value)e', get_cmd=':WFMI:YOF?'),
        QReal('Y Zero', set_cmd=':WFMI:YZER %(value)e', get_cmd=':WFMI:YZER?'),
        QVector('Histogram', get_cmd='HIStogram:DATa?'),
        QReal('Histogram Start', get_cmd='HIStogram:STARt?'),
        QReal('Histogram End', get_cmd='HIStogram:END?')
    ]

    def resetHist(self):
        self.write('HIStogram:COUNt RESET')

    def get_Trace(self, ch=1, start=1, stop=100000):
        self.write(':DAT:SOU CH%d' % ch)
        self.write(':DAT:START %d' % start)
        self.write(':DAT:STOP %d' % stop)
        y = np.array(self.query_ascii_values('CURV?'))
        y_offset = self.getValue('Y Offset')
        y_scale = self.getValue('Y Mult')
        y_zero = self.getValue('Y Zero')
        y = (y-y_offset)*y_scale+y_zero
        x = np.arange(start-1, stop, 1)*self.getValue('X Step') + self.getValue('X Zero')
        return x, (y*10-self.getValue('Y Position', ch=ch))*self.getValue('Y Scale', ch=ch)
