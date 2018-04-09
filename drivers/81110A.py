import numpy as np
import time

from lab.device import BaseDriver
from lab.device import QReal, QOption, QInteger, QString, QVector


class Driver(BaseDriver):
    error_command = ''
    surport_models = ['81110A']

    quants = [

        QReal('CH1 Delay',unit='ns',set_cmd=':PULS:DEL1 %(value).2fNS',get_cmd=':PULS:DEL1?'),
        QReal('CH1 Width',unit='ns',set_cmd=':PULS:WIDT1 %(value).2fNS',get_cmd=':PULS:WIDT1?'),
        QReal('CH1 High Level',unit='V',set_cmd=':VOLT1:HIGH %(value).2fV',get_cmd=':VOLT1:HIGH?'),
        QReal('CH1 Low Level',unit='mV',set_cmd=':VOLT1:LOW %(value).2fMV',get_cmd=':VOLT1:LOW?'),
        QReal('CH1 Offset',unit='mV',set_cmd=':VOLT1:OFF %(value).2fMV',get_cmd=':VOLT1:OFF?'),
        QReal('Trigger Level',unit='V',set_cmd=':ARM:LEV %(value).2fV',get_cmd=':ARM:LEV?'),
        QReal('Trigger Period',unit='ns',set_cmd=':ARM:PER %(value).2fns',get_cmd=':ARM:PER?'),


        #QReal('T0 Amplitude', unit='V', set_cmd='LAMP 0,%(value).2f', get_cmd='LAMP?0'),
    ]
