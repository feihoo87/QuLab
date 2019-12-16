# -*- coding: utf-8 -*-
from qulab.Driver import BaseDriver, QOption, QReal, QList, QInteger
from . import LabBrick_LMS_Wrapper

import logging
log = logging.getLogger(__name__)

class Driver(BaseDriver):
    """ This class implements a Lab Brick generator"""

    __log__=log
    
    support_models = [  'LMS-103', 'LMS-123', 'LMS-203', 'LMS-802', 'LMS-163', 'LMS-232D',
                        'LMS-402D', 'LMS-602D', 'LMS-451D', 'LMS-322D', 'LMS-271D', 'LMS-152D',
                        'LMS-751D', 'LMS-252D', 'LMS-6123LH', 'LMS-163LH', 'LMS-802LH',
                        'LMS-802DX', 'LMS-183DX']

    quants = [
        QReal('Frequency', unit='Hz',),
        QReal('Power', unit='dBm',),
        QOption('Output',options=[('OFF', False), ('ON', True)]),
        QOption('Reference',options=[('Internal', True), ('External', False)])
        ]

    def __init__(self, addr, **kw):
        '''addr is Serial number!'''
        super().__init__(self, addr, **kw)
        self.model='LMS'
        self.Serial=int(addr)

    def performOpen(self, options={}):
        """Perform the operation of opening the instrument connection"""
        # open connection
        self.handle = LabBrick_LMS_Wrapper.LabBrick_Synthesizer(bTestMode=False)
        self.handle.initDevice(self.Serial)


    def performClose(self, bError=False, options={}):
        """Perform the close instrument connection operation"""
        # do not check for error if close was called with an error
        try:
            self.handle.closeDevice()
        except:
            # never return error here
            pass


    def performSetValue(self, quant, value, sweepRate=0.0, options={}):
        """Perform the Set Value instrument operation. This function should
        return the actual value set by the instrument"""

        # proceed depending on command
        if quant.name == 'Frequency':
            # make sure value is in range
            value = self.handle.setFrequency(value)
        elif quant.name == 'Power':
            self.handle.setPowerLevel(value)
        elif quant.name == 'Output':
            # self.handle.setRFOn(bool(value))
            options=dict(quant.options)
            self.handle.setRFOn(bool(options[value]))
        elif quant.name == 'Reference':
            # self.handle.setUseInternalRef(bool(value))
            options=dict(quant.options)
            self.handle.setUseInternalRef(bool(options[value]))
        # elif quant.name == 'External pulse modulation':
        #     self.handle.setExternalPulseMod(bool(value))
        # elif quant.name in ('Internal pulse modulation', 'Pulse time', 'Pulse period'):
        #     # special case for internal pulse modulation, set all config at once
        #     bOn = self.getValue('Internal pulse modulation')
        #     pulseTime = self.getValue('Pulse time')
        #     pulsePeriod = self.getValue('Pulse period')
        #     self.handle.setInternalPulseMod(pulseTime, pulsePeriod, bOn)
        # return value


    def performGetValue(self, quant, options={}):
        """Perform the Get Value instrument operation"""
        # proceed depending on command
        if quant.name == 'Frequency':
            value = self.handle.getFrequency()
        elif quant.name == 'Power':
            value = self.handle.getPowerLevel()
        elif quant.name == 'Output':
            value = self.handle.getRFOn()
        elif quant.name == 'Reference':
            value = self.handle.getUseInternalRef()
        # elif quant.name == 'Internal pulse modulation':
        #     value = self.handle.getInternalPulseMod()
        # elif quant.name == 'Pulse time':
        #     value = self.handle.getPulseOnTime()
        # elif quant.name == 'Pulse period':
        #     value = self.handle.getPulsePeriod()
        # elif quant.name == 'External pulse modulation':
        #     value = self.handle.getExternalPulseMod()
        # return value
        return value




if __name__ == '__main__':
	pass
