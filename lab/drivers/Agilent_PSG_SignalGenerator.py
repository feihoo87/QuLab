# -*- coding: utf-8 -*-
import numpy as np

from lab.device import BaseDriver
from lab.device import QReal, QOption, QInteger, QString, QVector

class Driver(BaseDriver):
    surport_models = ['E8257D', 'SMF100A', 'SMB100A']

    quants = [
        QReal('Frequency', unit='Hz',
          set_cmd=':FREQ %(value).13e',
          get_cmd=':FREQ?'),

        QReal('Power', unit='dBm',
          set_cmd=':POWER %(value).8e',
          get_cmd=':POWER?'),

        QOption('Output',
          set_cmd=':OUTP %(option)s', options=[('OFF', 'OFF'), ('ON', 'ON')]),
    ]
