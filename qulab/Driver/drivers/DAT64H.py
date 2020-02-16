import numpy as np
import logging
log = logging.getLogger(__name__)

from qulab.Driver import SerialDriver, QReal, QOption


class Driver(SerialDriver):
    support_models = ['DAT64H']
    __log__ = log

    quants = [

        QReal('ATT',
              value=0,
              unit='dB',
              set_cmd='ATT %(value).1f',
              get_cmd='ATT?'),
 
        QOption('Display',
                set_cmd='*DISPLAY %(option)s', 
                options=[('OFF', 'OFF'), ('ON', 'ON')]),

    ]