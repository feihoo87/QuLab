# -*- coding: utf-8 -*-
import numpy as np

from qulab import BaseDriver, QInteger, QOption, QReal, QString, QVector

from  .AWGboard import AWGBoard


class Driver(BaseDriver):
    support_models = ['PG_AWG']

    quants = [
        QReal('Offset',unit='V',ch=1,),
        QReal('Amplitude',unit='VPP',ch=1,),
        ]

    def __init__(self, **kw):
        BaseDriver.__init__(self, **kw)
        self.model='PG_AWG'
        self.ip=kw['IP']

    def performOpen(self):
        awg = AWGBoard()
        awg.connect(self.ip)
        # 初始化AWG
        awg.InitBoard()
        self.awg=awg

    def performSetValue(self, quant, value, ch=1, **kw):
        if quant.name == 'Offset':
            self.awg.SetOffsetVolt(channel=ch, offset_volt=value)
        if quant.name == 'Amplitude':
            self.awg.set_channel_gain(ch=ch,gain=value)



    def AWG_run(self, array, ch=1):
        wave_list = []
        wave_list.append(self.awg.gen_wave_unit(array, '触发', 0))
        self.awg.wave_compile(ch, wave_list)
        self.awg.Start(ch)
