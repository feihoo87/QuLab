import numpy as np
import time

from lab.device import BaseDriver
from lab.device import QReal, QOption, QInteger, QString, QVector


class Driver(BaseDriver):
    error_command = ''
    surport_models = ['81110A']

    quants = [

        QReal('Delay',unit='ns',set_cmd=':PULS:DEL%(ch)d %(value).2fNS',get_cmd=':PULS:DEL%(ch)d?'),
        QReal('Width',unit='ns',set_cmd=':PULS:WIDT%(ch)d %(value).2fNS',get_cmd=':PULS:WIDT%(ch)d?'),
        QReal('High Level',unit='V',set_cmd=':VOLT%(ch)d:HIGH %(value).2fV',get_cmd=':VOLT%(ch)d:HIGH?'),
        QReal('Low Level',unit='mV',set_cmd=':VOLT%(ch)d:LOW %(value).2fMV',get_cmd=':VOLT%(ch)d:LOW?'),
        QReal('Offset',unit='mV',set_cmd=':VOLT%(ch)d:OFF %(value).2fMV',get_cmd=':VOLT%(ch)d:OFF?'),
        QReal('Trigger Level',unit='V',set_cmd=':ARM:LEV %(value).2fV',get_cmd=':ARM:LEV?'),
        QReal('Trigger Period',unit='ns',set_cmd=':ARM:PER %(value).2fns',get_cmd=':ARM:PER?'),


        #QReal('T0 Amplitude', unit='V', set_cmd='LAMP 0,%(value).2f', get_cmd='LAMP?0'),
    ]
