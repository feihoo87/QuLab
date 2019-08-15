# -*- coding: utf-8 -*-
import numpy as np

from qulab.Driver import visaDriver, QOption, QReal


class Driver(visaDriver):
    support_models = ['IT6302']

    quants = [
        QReal(
            'CH1 Voltage',
            unit='V',
            #set_cmd='SYST:REM;INST CH1;VOLT %(value).13e'
            set_cmd='INST CH1;VOLT %(value).13e',
            get_cmd='MEAS? CH1'),
        QReal(
            'CH1 Current',
            unit='A',
            #set_cmd='SYST:REM;INST CH1;CURR %(value).13e'
            set_cmd='INST CH1;CURR %(value).13e',
            get_cmd='MEAS:CURR? CH1'),
        QReal(
            'CH2 Voltage',
            unit='V',
            #set_cmd='SYST:REM;INST CH2;VOLT %(value).13e'
            set_cmd='INST CH2;VOLT %(value).13e',
            get_cmd='MEAS? CH2'),
        QReal(
            'CH2 Current',
            unit='A',
            #set_cmd='SYST:REM;INST CH2;CURR %(value).13e'
            set_cmd='INST CH2;CURR %(value).13e',
            get_cmd='MEAS:CURR? CH2'),
        QReal(
            'CH3 Voltage',
            unit='V',
            #set_cmd='SYST:REM;INST CH3;VOLT %(value).13e'
            set_cmd='INST CH3;VOLT %(value).13e',
            get_cmd='MEAS? CH3'),
        QReal(
            'CH3 Current',
            unit='A',
            #set_cmd='SYST:REM;INST CH3;CURR %(value).13e'
            set_cmd='INST CH3;CURR %(value).13e',
            get_cmd='MEAS:CURR? CH3'),
        QReal(
            'Voltage',
            unit='V',
            #set_cmd='SYST:REM;INST CH3;VOLT %(value).13e'
            set_cmd='INST CH%(ch)d;VOLT %(value).13e',
            get_cmd='MEAS? CH%(ch)d'),
        QReal(
            'Current',
            unit='A',
            #set_cmd='SYST:REM;INST CH3;CURR %(value).13e'
            set_cmd='INST CH%(ch)d;CURR %(value).13e',
            get_cmd='MEAS:CURR? CH%(ch)d'),
        QReal('Voltage Limit',
              unit='V',
              set_cmd='INST CH%(ch)d;VOLT %(value).13e',
              get_cmd='INST CH%(ch)d;VOLT?'),
        QReal('Current Limit',
              unit='A',
              set_cmd='INST CH%(ch)d;CURR %(value).13e',
              get_cmd='INST CH%(ch)d;CURR?'),
        QOption('Output',
                set_cmd='OUTP %(option)s',
                get_cmd='OUTP:STAT?',
                options=[('OFF', '0'), ('ON', '1')]),
        QOption('Combine',
                set_cmd='INST:COM:%(option)s',
                get_cmd='INST:COM?',
                options=[('Parallel', 'Parallel'), ('Series', 'Series'),
                         ('OFF', 'OFF')]),
    ]

    def performOpen(self):
        super(Driver,self).performOpen()
        self.write('SYST:REM')

    def performClose(self):
        self.write('SYST:LOC')
