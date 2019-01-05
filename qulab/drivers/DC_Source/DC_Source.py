# -*- coding: utf-8 -*-
import numpy as np

from qulab import BaseDriver, QInteger, QOption, QReal, QString, QVector

from .Highfine_DCsource import setvol

# class quantanti():
class Driver(BaseDriver):
    support_models = ['Highfine_DCsource']
    quants = [
        QReal('Offset', value=0, ch=0),


        # QOption('Channel', value = '0',
        #     options = [
        #         ('1',   2 ),   ('2',    4),
        #         ('3',   4),
        #     ])

            ]
    #
    # def __init__(self, **kw):
    #     BaseDriver.__init__(self, **kw)
    #     self.Serial = kw['Serial']


    # def __init__(self):
    #     """
    #     Constructor
    #
    #     @param parent reference to the parent widget
    #     @type QWidget
    #     """
    #     self.udpSocketClient = UDPSocketClient()
    #     # self.dValue = 0.0
    #     self.volValue = 1.0
    #
    #     # Set channel 1 as default
    #     self.sendCmdChnnelNum(0)
    #
    def performSetValue(self, quant, value, ch=0, **kw):
        if quant.name == 'Offset':
            setvol(value,ch=ch)
