# -*- coding: utf-8 -*-
import time

import numpy as np

from qulab import BaseDriver, QInteger, QOption, QReal, QString, QVector


class Driver(BaseDriver):
    error_command = 'LERR?'
    support_models = ['DG645']

    quants = [
        QReal('Trigger Rate', unit='Hz', set_cmd='TRAT %(value).6E', get_cmd='TRAT?'),

        QReal('T0 Amplitude', unit='V', set_cmd='LAMP 0,%(value).2f', get_cmd='LAMP?0'),
        QReal('T0 Offset', unit='V', set_cmd='LOFF 0,%(value).2f', get_cmd='LOFF?0'),
        QReal('T0 Length', unit='us', set_cmd='DLAY 1,0,%(value).6E', get_cmd='DLAY?1'),
        QOption('T0 Polarity', set_cmd='LPOL 0,%(option)s', get_cmd='LPOL?0',
                options=[('pos', '1'),('neg', '0')]),

        QReal('AB Amplitude', unit='V', set_cmd='LAMP 1,%(value).2f', get_cmd='LAMP?1'),
        QReal('AB Offset', unit='V', set_cmd='LOFF 1,%(value).2f', get_cmd='LOFF?1'),
        QReal('AB Delay', unit='us', set_cmd='DLAY 2,0,%(value).6E', get_cmd='DLAY?2'),
        QReal('AB Length', unit='us', set_cmd='DLAY 3,2,%(value).6E', get_cmd='DLAY?3'),
        QReal('A Delay', unit='us', set_cmd='DLAY 2,0,%(value).6E', get_cmd='DLAY?2'),
        QReal('B Delay', unit='us', set_cmd='DLAY 3,0,%(value).6E', get_cmd='DLAY?3'),
        QOption('AB Polarity', set_cmd='LPOL 1,%(option)s', get_cmd='LPOL?1',
                options=[('pos', '1'),('neg', '0')]),

        QReal('CD Amplitude', unit='V', set_cmd='LAMP 2,%(value).2f', get_cmd='LAMP?2'),
        QReal('CD Offset', unit='V', set_cmd='LOFF 2,%(value).2f', get_cmd='LOFF?2'),
        QReal('CD Delay', unit='us', set_cmd='DLAY 4,0,%(value).6E', get_cmd='DLAY?4'),
        QReal('CD Length', unit='us', set_cmd='DLAY 5,4,%(value).6E', get_cmd='DLAY?5'),
        QReal('C Delay', unit='us', set_cmd='DLAY 4,0,%(value).6E', get_cmd='DLAY?4'),
        QReal('D Delay', unit='us', set_cmd='DLAY 5,0,%(value).6E', get_cmd='DLAY?5'),
        QOption('CD Polarity', set_cmd='LPOL 2,%(option)s', get_cmd='LPOL?2',
                options=[('pos', '1'),('neg', '0')]),

        QReal('EF Amplitude', unit='V', set_cmd='LAMP 3,%(value).2f', get_cmd='LAMP?3'),
        QReal('EF Offset', unit='V', set_cmd='LOFF 3,%(value).2f', get_cmd='LOFF?3'),
        QReal('EF Delay', unit='us', set_cmd='DLAY 6,0,%(value).6E', get_cmd='DLAY?6'),
        QReal('EF Length', unit='us', set_cmd='DLAY 7,6,%(value).6E', get_cmd='DLAY?7'),
        QReal('E Delay', unit='us', set_cmd='DLAY 6,0,%(value).6E', get_cmd='DLAY?6'),
        QReal('F Delay', unit='us', set_cmd='DLAY 7,0,%(value).6E', get_cmd='DLAY?7'),
        QOption('EF Polarity',set_cmd='LPOL 3,%(option)s', get_cmd='LPOL?3',
                options=[('pos', '1'),('neg', '0')]),

        QReal('GH Amplitude', unit='V', set_cmd='LAMP 4,%(value).2f', get_cmd='LAMP?4'),
        QReal('GH Offset', unit='V', set_cmd='LOFF 4,%(value).2f', get_cmd='LOFF?4'),
        QReal('GH Delay', unit='us', set_cmd='DLAY 8,0,%(value).6E', get_cmd='DLAY?8'),
        QReal('GH Length', unit='us', set_cmd='DLAY 9,8,%(value).6E', get_cmd='DLAY?9'),
        QReal('G Delay', unit='us', set_cmd='DLAY 8,0,%(value).6E', get_cmd='DLAY?8'),
        QReal('H Delay', unit='us', set_cmd='DLAY 9,0,%(value).6E', get_cmd='DLAY?9'),
        QOption('GH Polarity', set_cmd='LPOL 4,%(option)s', get_cmd='LPOL?4',
                options=[('pos', '1'),('neg', '0')])
    ]


    def performGetValue(self, quant, **kw):
        get_Delays = ['T0 Length','AB Delay','AB Length','A Delay','B Delay',
            'CD Delay','CD Length','C Delay','D Delay',
            'EF Delay','EF Length','E Delay','F Delay',
            'GH Delay','GH Length','G Delay','H Delay'
        ]
        if quant.name in get_Delays and quant.get_cmd is not '':
            cmd = quant._formatGetCmd(**kw)
            res = self.query_ascii_values(cmd)
            quant.value= res[1]
            return res[0],quant.value*1e6 # res[0] is the chanel that related ; quant.value : 's' convert to 'us'
        else:
            return super(Driver, self).performGetValue(quant, **kw)

    def performSetValue(self, quant,value, **kw):
        set_Delays = ['T0 Length','AB Delay','AB Length','A Delay','B Delay',
            'CD Delay','CD Length','C Delay','D Delay',
            'EF Delay','EF Length','E Delay','F Delay',
            'GH Delay','GH Length','G Delay','H Delay'
        ]
        if quant.name in set_Delays and quant.set_cmd is not '':
            value=value/1e6  # 'us' convert to 's'
            quant.value = value
            cmd = quant._formatSetCmd(value,**kw)
            self.write(cmd)
        else:
            return super(Driver, self).performSetValue(quant,value, **kw)
