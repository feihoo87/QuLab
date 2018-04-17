# -*- coding: utf-8 -*-
import time

import numpy as np

from lab.device import BaseDriver, QInteger, QOption, QReal, QString, QVector


class Driver(BaseDriver):
    error_command = '*ESR?'
    support_models = ['AFG3102']



    quants = [
        QOption('Output',ch=1,
        set_cmd='OUTP%(ch)d %(option)s', get_cmd='OUTP%(ch)d?'
        options=[('OFF', 'OFF'), ('ON', 'ON')]),  # must set chanel

        QOption('Function',ch=1,set_cmd='SOUR%(ch)d:FUNC %(option)s',get_cmd='SOUR%(ch)d:FUNC?',
            options=[('Sin','SIN'),('Square','SQU'),('Pulse','PULS'),('Ramp','RAMP'),
                ('PRNoise','PRN'),('DC','DC'),('SINC','SINC'),('Gaussian','GAUS'),
                ('Lorentz','LOR'),('Erise','ERIS'),('Edecay','EDEC'),('Haversine','HAV'),
                ('User','USER'),('User2','USER2')]),

        QReal('Frequency',unit='Hz',ch=1,set_cmd='SOUR%(ch)d:FREQ %(value)e%(unit)s',get_cmd='SOUR%(ch)d:FREQ?'),
        QReal('Phase',unit='rad',ch=1,set_cmd='SOUR%(ch)d:PHAS %(value)f%(unit)s',get_cmd='SOUR%(ch)d:PHAS?'),
        QReal('Pulse Delay',unit='s',ch=1,set_cmd='SOUR%(ch)d:PULS:DEL %(value).9e%(unit)s',get_cmd='SOUR%(ch)d:PULS:DEL?'),
        QReal('Pulse Period',unit='s',ch=1,set_cmd='SOUR%(ch)d:PULS:PER %(value).9e%(unit)s',get_cmd='SOUR%(ch)d:PULS:PER?'),
        QReal('Pulse Width',unit='s',ch=1,set_cmd='SOUR%(ch)d:PULS:WIDT %(value).9e%(unit)s',get_cmd='SOUR%(ch)d:PULS:WIDT?'),
        #Burst Mode
        QReal('Burst Tdelay',unit='s',ch=1,set_cmd='SOUR%(ch)d:BURS:TDEL %(value).9e%(unit)s',get_cmd='SOUR%(ch)d:BURS:TDEL?'),
        QReal('Burst Ncycles',ch=1,set_cmd='SOUR%(ch)d:BURS:NCYC %(value)d',get_cmd='SOUR%(ch)d:BURS:NCYC?'),
        ##
        QReal('Frequency',unit='Hz',ch=1,set_cmd='SOUR%(ch)d:FREQ %(value)e%(unit)s',get_cmd='SOUR%(ch)d:FREQ?'),
        QReal('Phase',unit='DEG',ch=1,set_cmd='SOUR%(ch)d:PHAS %(value)f%(unit)s',get_cmd='SOUR%(ch)d:PHAS?'),
        QReal('High Level',unit='V',ch=1,set_cmd='SOUR%(ch)d:VOLT:HIGH %(value)f%(unit)s',get_cmd='SOUR%(ch)d:VOLT:HIGH?'),
        QReal('Low Level',unit='V',ch=1,set_cmd='SOUR%(ch)d:VOLT:LOW %(value)f%(unit)s',get_cmd='SOUR%(ch)d:VOLT:LOW?'),
        QReal('Offset',unit='V',ch=1,set_cmd='SOUR%(ch)d:VOLT:OFFS %(value)f%(unit)s',get_cmd='SOUR%(ch)d:VOLT:OFFS?'),
        QReal('Amplitude',unit='VPP',ch=1,set_cmd='SOUR%(ch)d:VOLT:AMPL %(value)f%(unit)s',get_cmd='SOUR%(ch)d:VOLT:AMPL?'),
    ]
