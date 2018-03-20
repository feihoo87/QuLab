# -*- coding: utf-8 -*-
import numpy as np
from lab.device import BaseDriver, QInteger, QOption, QReal, QVector


class Driver(BaseDriver):
    surport_models = ['E8363C', 'R&S ZNB', 'R&S ZNBT']

    quants = [
        QReal('Power', value=-20, unit='dBm', set_cmd='SOUR:POW1 %(value)e', get_cmd='SOUR:POW1?'),
        QOption('Sweep', value='ON',
          set_cmd='INIT:CONT %(option)s', options=[('OFF', 'OFF'), ('ON', 'ON')]),
        QInteger('Number of points', value=201, unit='',
          set_cmd='SENS:SWE:POIN %(value)d', get_cmd='SENS:SWE:POIN?'),
        QOption('Format', value='MLOG',
          set_cmd='CALC:FORM %(option)s', get_cmd='CALC:FORM?',
          options=[('Mlinear', 'MLIN'),
                   ('Mlog', 'MLOG'),
                   ('Phase', 'PHAS'),
                   ('Unwrapped phase', 'UPH'),
                   ('Imag', 'IMAG'),
                   ('Real', 'REAL'),
                   ('Polar', 'POL'),
                   ('Smith', 'SMIT'),
                   ('SWR', 'SWR'),
                   ('Group Delay', 'GDEL')])
    ]

    '''
    def performSetValue(self, quant, value, **kw):
        if quant.name == 'Power':
            self.setValue('Power:Start', value)
            self.setValue('Power:Center', value)
            self.setValue('Power:Stop', value)
        else:
            super(Driver, self).performSetValue(quant, value, **kw)

    def performGetValue(self, quant, **kw):
        if quant.name == 'Power':
            return self.getValue('Power:Center')
        else:
            return super(Driver, self).performGetValue(quant, **kw)
    '''

    def get_Trace(self, ch=1):
        '''Get trace'''
        #Select the measurement
        self.pna_select(ch)

        #Stop the sweep
        self.setValue('Sweep', 'OFF')
        #Begin a measurement
        self.write('INIT:IMM')
        self.write('*WAI')
        #Get the data
        self.write('FORMAT:BORD NORM')
        self.write('FORMAT ASCII')
        data = self.query_ascii_values("CALC%d:DATA? FDATA" % ch)
        #Start the sweep
        self.setValue('Sweep', 'ON')
        return np.array(data)

    def get_S(self, ch=1):
        '''Get the complex value of S paramenter'''
        #Select the measurement
        self.pna_select(ch)

        #Stop the sweep
        self.setValue('Sweep', 'OFF')
        #Begin a measurement
        self.write('INIT:IMM')
        self.write('*WAI')
        #Get the data
        self.write('FORMAT:BORD NORM')
        self.write('FORMAT ASCII')
        data = self.query_ascii_values("CALC%d:DATA? SDATA" % ch)
        data = np.asarray(data)
        #Start the sweep
        self.setValue('Sweep', 'ON')
        return data[::2]+1j*data[1::2]

    def pna_select(self, ch=1):
        '''Select the measurement'''
        if self.model == 'E8363C':
            quote = '" '
        elif self.model in ['R&S ZNB', 'R&S ZNBT']:
            quote = "' "
        msg = self.query('CALC%d:PAR:CAT?' % ch).strip(quote)
        measname = msg.split(',')[0]
        self.write('CALC%d:PAR:SEL "%s"' % (ch, measname))

    def get_Frequency(self, ch=1):
        """Return the frequency of pna measurement"""

        #Select the measurement
        self.pna_select(ch)
        if self.model == 'E8363C':
            cmd = 'CALC:X?'
        elif self.model in ['R&S ZNB', 'R&S ZNBT']:
            cmd = 'CALC:DATA:STIM?'
        return np.asarray(self.query_ascii_values(cmd))

    def set_segments(self, segments=[], form='Start Stop'):
        if form == 'Start Stop':
            cmd = ','.join(['SENS:SEGM:LIST SSTOP'].extend([
                '1,%(num)d,%(start)g,%(stop)g,%(IFBW)%g,0,%(power)%g' % segment for segment in segments
            ]))
        else:
            cmd = ','.join(['SENS:SEGM:LIST CSPAN'].extend([
                '1,%(num)d,%(center)g,%(span)g,%(IFBW)%g,0,%(power)%g' % segment for segment in segments
            ]))
        self.write('FORMAT ASCII')
        self.write(cmd)
