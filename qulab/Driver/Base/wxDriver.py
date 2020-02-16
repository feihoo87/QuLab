# import logging
import numpy as np

from .BaseDriver import BaseDriver
from .quant import QReal, QInteger, QString, QOption, QBool, QVector, QList, newcfg

from .wxAWG_API.tewx import TEWXAwg

# log = logging.getLogger(__name__)


class wxDriver(BaseDriver):
    '''Tabor Electronics WX AWG:
        'WX2184' ,'WX2184C','WX1284' ,'WX1284C','WX2182C','WX1282C'.
    '''

    def __init__(self, addr=None, timeout=3, paranoia_level=1, **kw):
        super().__init__(addr, timeout, **kw)
        self.paranoia_level=paranoia_level

    def __repr__(self):
        return 'wxDriver(addr=%s,model=%s)' % (self.addr,self.model)

    def performOpen(self, **kw):
        self.handle=TEWXAwg(instr_addr=self.addr, tcp_timeout=self.timeout, paranoia_level=self.paranoia_level)
        self.model=self.handle.model_name

    def performClose(self, **kw):
        self.handle.close()

    def performOPC(self):
        opc=int(self.query("*OPC?"))
        return opc

    def query(self, message):
        self.log.debug("%s << %s", str(self.handle), message)
        try:
            res = self.handle.send_query(message)
        except:
            self.log.exception("%s << %s", str(self.handle), message)
            raise
        self.log.debug("%s >> %s", str(self.handle), res)
        return res

    def write(self, message):
        """Send message to the instrument."""
        self.log.debug("%s << %s", str(self.handle), message)
        try:
            _ = self.handle.send_cmd(message)
        except:
            self.log.exception("%s << %s", str(self.handle), message)
            raise

    
    def build_wave(self, points):
        '''Build Wave, refer TEWXAwg.build_sine_wave

        :param points: points array, 'list' or 'numpy.array'.
        :returns: `numpy.array` with the wave data (DAC values)
        '''

        dac_min = self.handle.get_dev_property('min_dac_val', 0)
        dac_max = self.handle.get_dev_property('max_dac_val', 2**14-1)

        # wav_len = len(points)

        zero_val = (dac_min + dac_max) / 2.0
        amplitude = (dac_max - dac_min) / 2.0
        y = np.array(points) * amplitude + zero_val
        y = np.round(y)
        y = np.clip(y, dac_min, dac_max)

        y = y.astype(np.uint16)
        return y
    