# -*- coding: utf-8 -*-
import numpy as np

from lab.device import BaseDriver, QInteger, QOption, QReal, QString, QVector


class Driver(BaseDriver):
    support_models = ['E8257D', 'SMF100A', 'SMB100A','SGS100A']

    quants = [
        QReal('Frequency', unit='Hz',
          set_cmd=':FREQ %(value).13e%(unit)s',
          get_cmd=':FREQ?'),

        QReal('Power', unit='dBm',
          set_cmd=':POWER %(value).8e%(unit)s',
          get_cmd=':POWER?'),

        QOption('Output',
          set_cmd=':OUTP %(option)s', options=[('OFF', 'OFF'), ('ON', 'ON')]),
    ]
