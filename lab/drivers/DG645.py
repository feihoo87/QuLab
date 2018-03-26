# -*- coding: utf-8 -*-
import time

import numpy as np

from lab.device import BaseDriver, QInteger, QOption, QReal, QString, QVector


class Driver(BaseDriver):
    error_command = ''
    support_models = ['DG645']

    quants = [
        QReal('Trigger Rate', unit='Hz', set_cmd='TRAT %(value).6E', get_cmd='TRAT?'),

        QReal('T0 Amplitude', unit='V', set_cmd='LAMP 0,%(value).2f', get_cmd='LAMP?0'),
        QReal('T0 Offset', unit='V', set_cmd='LOFF 0,%(value).2f', get_cmd='LOFF?0'),
        QReal('T0 Length', unit='s', set_cmd='DLAY 1,0,%(value).6E', get_cmd='DLAY?1'),
        QOption('T0 Polarity', set_cmd='LPOL 0,%(option)s', get_cmd='LPOL?0',
                options=[('pos', '1'),('neg', '0')]),

        QReal('AB Amplitude', unit='V', set_cmd='LAMP 1,%(value).2f', get_cmd='LAMP?1'),
        QReal('AB Offset', unit='V', set_cmd='LOFF 1,%(value).2f', get_cmd='LOFF?1'),
        QReal('AB Delay', unit='s', set_cmd='DLAY 2,0,%(value).6E', get_cmd='DLAY?2'),
        QReal('AB Length', unit='s', set_cmd='DLAY 3,2,%(value).6E', get_cmd='DLAY?3'),
        QOption('AB Polarity', set_cmd='LPOL 1,%(option)s', get_cmd='LPOL?1',
                options=[('pos', '1'),('neg', '0')]),

        QReal('CD Amplitude', unit='V', set_cmd='LAMP 2,%(value).2f', get_cmd='LAMP?2'),
        QReal('CD Offset', unit='V', set_cmd='LOFF 2,%(value).2f', get_cmd='LOFF?2'),
        QReal('CD Delay', unit='s', set_cmd='DLAY 4,0,%(value).6E', get_cmd='DLAY?4'),
        QReal('CD Length', unit='s', set_cmd='DLAY 5,4,%(value).6E', get_cmd='DLAY?5'),
        QOption('CD Polarity', set_cmd='LPOL 2,%(option)s', get_cmd='LPOL?2',
                options=[('pos', '1'),('neg', '0')]),

        QReal('EF Amplitude', unit='V', set_cmd='LAMP 3,%(value).2f', get_cmd='LAMP?3'),
        QReal('EF Offset', unit='V', set_cmd='LOFF 3,%(value).2f', get_cmd='LOFF?3'),
        QReal('EF Delay', unit='s', set_cmd='DLAY 6,0,%(value).6E', get_cmd='DLAY?6'),
        QReal('EF Length', unit='s', set_cmd='DLAY 7,6,%(value).6E', get_cmd='DLAY?7'),
        QOption('EF Polarity',set_cmd='LPOL 3,%(option)s', get_cmd='LPOL?3',
                options=[('pos', '1'),('neg', '0')]),

        QReal('GH Amplitude', unit='V', set_cmd='LAMP 4,%(value).2f', get_cmd='LAMP?4'),
        QReal('GH Offset', unit='V', set_cmd='LOFF 4,%(value).2f', get_cmd='LOFF?4'),
        QReal('GH Delay', unit='s', set_cmd='DLAY 8,0,%(value).6E', get_cmd='DLAY?8'),
        QReal('GH Length', unit='s', set_cmd='DLAY 9,8,%(value).6E', get_cmd='DLAY?9'),
        QOption('GH Polarity', set_cmd='LPOL 4,%(option)s', get_cmd='LPOL?4',
                options=[('pos', '1'),('neg', '0')])
    ]
