# -*- coding: utf-8 -*-
import time

import numpy as np

from lab.device import BaseDriver, QInteger, QOption, QReal, QString, QVector


class Driver(BaseDriver):
    error_command = ''
    support_models = ['AFG3102']



    quants = [
        QOption('Output',
        set_cmd='OUTP%(ch)d %(option)s', get_cmd='OUTP%(ch)d?'
        options=[('OFF', 'OFF'), ('ON', 'ON')]),  # must set chanel

        QOption('Function',set_cmd='SOUR%(ch)d:FUNC %(option)s',get_cmd='SOUR%(ch)d:FUNC?',
            options=[('Sin','SIN'),('Square','SQU'),('Pulse','PULS'),('Ramp','RAMP'),
                ('PRNoise','PRN'),('DC','DC'),('SINC','SINC'),('Gaussian','GAUS'),
                ('Lorentz','LOR'),('Erise','ERIS'),('Edecay','EDEC'),('Haversine','HAV'),
                ('User','USER'),('User2','USER2')]),

        QReal('Frequency',unit='Hz',set_cmd='SOUR%(ch)d:FREQ %(value)e',get_cmd='SOUR%(ch)d:FREQ?'),
        QReal('Phase',unit='rad',set_cmd='SOUR%(ch)d:PHAS %(value)f',get_cmd='SOUR%(ch)d:PHAS?'),
        QReal('Pulse Delay',unit='s',set_cmd='SOUR%(ch)d:PULS:DEL %(value).9e',get_cmd='SOUR%(ch)d:PULS:DEL?'),
        QReal('High Level',unit='V',set_cmd='SOUR%(ch)d:VOLT:HIGH %(value)f',get_cmd='SOUR%(ch)d:VOLT:HIGH?'),
        QReal('Low Level',unit='V',set_cmd='SOUR%(ch)d:VOLT:LOW %(value)f',get_cmd='SOUR%(ch)d:VOLT:LOW?'),
        QReal('Offset',unit='V',set_cmd='SOUR%(ch)d:VOLT:OFFS %(value)f',get_cmd='SOUR%(ch)d:VOLT:OFFS?'),
        QReal('Amplitude',unit='V',set_cmd='SOUR%(ch)d:VOLT:AMPL %(value)f',get_cmd='SOUR%(ch)d:VOLT:AMPL?'),
    ]
