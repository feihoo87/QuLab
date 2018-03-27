# -*- coding: utf-8 -*-
import numpy as np

from lab.device import BaseDriver, QInteger, QOption, QReal, QString, QVector


class Driver(BaseDriver):
    support_models = ['IT6302']

    quants = [
        QReal('CH1 Voltage', unit='V',
          #set_cmd='SYST:REM;INST CH1;VOLT %(value).13e'
          set_cmd='INST CH1;VOLT %(value).13e',
          get_cmd='MEAS? CH1'),

        QReal('CH1 Current', unit='A',
          #set_cmd='SYST:REM;INST CH1;CURR %(value).13e'
          set_cmd='INST CH1;CURR %(value).13e',
          get_cmd='MEAS:CURR? CH1'),

        QReal('CH2 Voltage', unit='V',
          #set_cmd='SYST:REM;INST CH2;VOLT %(value).13e'
          set_cmd='INST CH2;VOLT %(value).13e',
          get_cmd='MEAS? CH2'),

        QReal('CH2 Current', unit='A',
          #set_cmd='SYST:REM;INST CH2;CURR %(value).13e'
          set_cmd='INST CH2;CURR %(value).13e',
          get_cmd='MEAS:CURR? CH2'),

        QReal('CH3 Voltage', unit='V',
          #set_cmd='SYST:REM;INST CH3;VOLT %(value).13e'
          set_cmd='INST CH3;VOLT %(value).13e',
          get_cmd='MEAS? CH3'),

        QReal('CH3 Current', unit='A',
          #set_cmd='SYST:REM;INST CH3;CURR %(value).13e'
          set_cmd='INST CH3;CURR %(value).13e',
          get_cmd='MEAS:CURR? CH3'),

        QOption('Output',
          set_cmd='OUTP %(option)s', options=[('OFF', 'OFF'), ('ON', 'ON')]),
    ]

    def performOpen(self):
        self.write('SYST:REM')
