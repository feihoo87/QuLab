import numpy as np
import time

from lab.device import BaseDriver
from lab.device import QReal, QOption, QInteger, QString, QVector


class Driver(BaseDriver):
    error_command = ''
    surport_models = ['81110A']

    quants = [

        QReal('Delay',ch=1,unit='s',set_cmd=':PULS:DEL%(ch)d %(value).9e%(unit)s',get_cmd=':PULS:DEL%(ch)d?'),
        QReal('Width',ch=1,unit='s',set_cmd=':PULS:WIDT%(ch)d %(value).9e%(unit)s',get_cmd=':PULS:WIDT%(ch)d?'),
        QReal('High Level',ch=1,unit='V',set_cmd=':VOLT%(ch)d:HIGH %(value).9e%(unit)s',get_cmd=':VOLT%(ch)d:HIGH?'),
        QReal('Low Level',ch=1,unit='V',set_cmd=':VOLT%(ch)d:LOW %(value).9e%(unit)s',get_cmd=':VOLT%(ch)d:LOW?'),
        QReal('Offset',ch=1,unit='V',set_cmd=':VOLT%(ch)d:OFF %(value).9e%(unit)s',get_cmd=':VOLT%(ch)d:OFF?'),
        QReal('Trigger Level',ch=1,unit='V',set_cmd=':ARM:LEV %(value).9e%(unit)s',get_cmd=':ARM:LEV?'),
        QReal('Trigger Period',ch=1,unit='s',set_cmd=':ARM:PER %(value).9e%(unit)s',get_cmd=':ARM:PER?'),


        #QReal('T0 Amplitude', unit='V', set_cmd='LAMP 0,%(value).9e', get_cmd='LAMP?0'),
    ]
