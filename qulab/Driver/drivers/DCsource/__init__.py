import logging
from qulab.Driver import (BaseDriver, QInteger, QOption, QReal, QVector)

from .VoltageSettingCore import (CalculateDValue, SetChannelNum, SetDefaultIP,
                                 SetDValue)

log = logging.getLogger('qulab.driver.DCSource')


class Driver(BaseDriver):

    CHs=[1,2,3,4]

    quants = [
        QReal('Offset', value=0, unit='V', ch=1),
            ]

    def __init__(self, addr, **kw):
        '''
        addr: ip, e.g. '192.168.1.6'
        '''
        super().__init__(addr, **kw)

    def performOpen(self):
        SetDefaultIP(self.addr)
        super().performOpen()

    def setVolt(self, volt, ch=1):
        log.info(f'Set volt of Channel {ch} to {volt}')
        SetDefaultIP(self.ip)
        SetChannelNum(ch-1, 0)
        SetDValue(CalculateDValue(volt))

    def performSetValue(self, quant, value, ch=1, **kw):
        if quant.name == 'Offset':
            self.setVolt(value,ch=ch)
