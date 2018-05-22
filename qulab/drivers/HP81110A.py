import numpy as np
import time

from lab.device import BaseDriver
from lab.device import QReal, QOption, QInteger, QString, QVector


class Driver(BaseDriver):
    error_command = ':SYST:ERR?'
    surport_models = ['HP81110A']

    quants = [

        QReal('Pulse Delay',ch=1,unit='s',set_cmd=':PULS:DEL%(ch)d %(value).9e%(unit)s',get_cmd=':PULS:DEL%(ch)d?'),
        QReal('Pulse Width',ch=1,unit='s',set_cmd=':PULS:WIDT%(ch)d %(value).9e%(unit)s',get_cmd=':PULS:WIDT%(ch)d?'),
        QReal('Pulse Period',ch=1,unit='s',set_cmd=':PULS:PER%(ch)d %(value).9e%(unit)s',get_cmd=':PULS:PER%(ch)d?'),

        #BURST mod, 2 chanels ,then use pulse delay/width/period to modify parameters
        QReal('Burst Ncycles',value=2, set_cmd=':TRIG:COUN %(value)d; :TRIG:SOUR INT; :DIG:PATT OFF',get_cmd=':TRIG:COUN?'),
        
        #double pulse mode,could use burst mode together, but can't change trigger delay
        #
        QReal('Double Pulse Delay',ch=1,unit='s',set_cmd=':PULS:DOUB%(ch)d:DEL %(value).9e%(unit)s',get_cmd=':PULS:DOUB%(ch)d:DEL?'),
        QOption('Double Pulse',ch=1, set_cmd=':PULS:DOUB%(ch)d %(option)s', get_cmd=':PULS:DOUB%(ch)d?',
                options=[('ON', 'ON'),('OFF', 'OFF'),('1','1'),('0','0')]),

        QReal('High Level',ch=1,unit='V',set_cmd=':VOLT%(ch)d:HIGH %(value).9e%(unit)s',get_cmd=':VOLT%(ch)d:HIGH?'),
        QReal('Low Level',ch=1,unit='V',set_cmd=':VOLT%(ch)d:LOW %(value).9e%(unit)s',get_cmd=':VOLT%(ch)d:LOW?'),
        QReal('Offset',ch=1,unit='V',set_cmd=':VOLT%(ch)d:OFF %(value).9e%(unit)s',get_cmd=':VOLT%(ch)d:OFF?'),
        QReal('Amplitude',ch=1,unit='V',set_cmd=':VOLT%(ch)d:AMP %(value).9e%(unit)s',get_cmd=':VOLT%(ch)d:AMP?'),

        QReal('Trigger Level',ch=1,unit='V',set_cmd=':ARM:LEV %(value).9e%(unit)s',get_cmd=':ARM:LEV?'),
        QReal('Trigger Period',ch=1,unit='s',set_cmd=':ARM:PER %(value).9e%(unit)s',get_cmd=':ARM:PER?'),

        QOption('Output',ch=1, set_cmd=':OUTP%(ch)d %(option)s', get_cmd=':OUTP%(ch)d?',
                options=[('ON', '1'),('OFF', '0')]),
    ]
