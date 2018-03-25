import numpy as np
import time

from lab.device import BaseDriver
from lab.device import QReal, QOption, QInteger, QString, QVector


class Driver(BaseDriver):
    error_command = ''
    surport_models = ['81110A']

    quants = [
        QReal('Frequency',unit='Hz',set_cmd='',get_cmd=''),
        QReal('High Level',unit='V',set_cmd='',get_cmd=''),
        QReal('Low Level',unit='V',set_cmd='',get_cmd=''),
        QReal()
    ]
