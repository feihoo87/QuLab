# -*- coding: utf-8 -*-
import numpy as np
from qulab import BaseDriver, QInteger, QOption, QReal, QVector


class Driver(BaseDriver):
    support_models = ['E8363B', 'E8363C', 'E5071C', 'ZNB20-2Port']

    quants = [
        QReal('Power',
              value=-20,
              unit='dBm',
              set_cmd='SOUR:POW %(value)e%(unit)s',
              get_cmd='SOUR:POW?'),
        QReal('Frequency center',
              value=5e9,
              unit='Hz',
              set_cmd='SENS:FREQ:CENT %(value)e%(unit)s',
              get_cmd='SENS:FREQ:CENT?'),
        QReal('Frequency span',
              value=2e9,
              unit='Hz',
              set_cmd='SENS:FREQ:SPAN %(value)e%(unit)s',
              get_cmd='SENS:FREQ:SPAN?'),
        QReal('Frequency start',
              value=4e9,
              unit='Hz',
              set_cmd='SENS:FREQ:STAR %(value)e%(unit)s',
              get_cmd='SENS:FREQ:STAR?'),
        QReal('Frequency stop',
              value=6e9,
              unit='Hz',
              set_cmd='SENS:FREQ:STOP %(value)e%(unit)s',
              get_cmd='SENS:FREQ:STOP?'),
        QVector('Frequency', unit='Hz'),
        QVector('Trace'),
        QVector('S'),
        QOption('Sweep',
                value='ON',
                set_cmd='INIT:CONT %(option)s',
                options=[('OFF', 'OFF'), ('ON', 'ON')]),
        QInteger('Number of points',
                 value=201,
                 unit='',
                 set_cmd='SENS:SWE:POIN %(value)d',
                 get_cmd='SENS:SWE:POIN?'),
        QOption('Format',
                value='MLOG',
                set_cmd='CALC:FORM %(option)s',
                get_cmd='CALC:FORM?',
                options=[('Mlinear', 'MLIN'), ('Mlog', 'MLOG'),
                         ('Phase', 'PHAS'), ('Unwrapped phase', 'UPH'),
                         ('Imag', 'IMAG'), ('Real', 'REAL'), ('Polar', 'POL'),
                         ('Smith', 'SMIT'), ('SWR', 'SWR'),
                         ('Group Delay', 'GDEL')]),
        QOption('SweepType',
                value='',
                set_cmd='SENS:SWE:TYPE %(option)s',
                get_cmd='SENS:SWE:TYPE?',
                options=[('Linear', 'LIN'), ('Log', 'LOG'), ('Power', 'POW'),
                         ('CW', 'CW'), ('Segment', 'SEGM'), ('Phase', 'PHAS')])
    ]
    '''
    def performSetValue(self, quant, value, **kw):
        if quant.name == 'Power':
            self.setValue('Power:Start', value)
            self.setValue('Power:Center', value)
            self.setValue('Power:Stop', value)
        else:
            super(Driver, self).performSetValue(quant, value, **kw)
    '''

    def performGetValue(self, quant, **kw):
        get_vector_methods = {
            'Frequency': self.get_Frequency,
            'Trace': self.get_Trace,
            'S': self.get_S,
        }
        if quant.name in get_vector_methods.keys():
            return get_vector_methods[quant.name](ch=kw.get('ch', 1))
        else:
            return super(Driver, self).performGetValue(quant, **kw)

    def get_Trace(self, ch=1):
        '''Get trace'''
        return self.get_S(ch, formated=True)

    def get_S(self, ch=1, formated=False):
        '''Get the complex value of S paramenter or formated data'''
        #Select the measurement
        self.pna_select(ch)

        #Stop the sweep
        self.setValue('Sweep', 'OFF')
        #Begin a measurement
        self.write('INIT:IMM')
        self.write('*WAI')
        #Get the data
        self.write('FORMAT:BORD NORM')
        if self.model in ['E5071C']:
            self.write(':FORM:DATA ASC')
            cmd = ("CALC%d:DATA:FDATA?" %
                   ch) if formated else ("CALC%d:DATA:SDATA?" % ch)
        else:
            self.write('FORMAT ASCII')
            cmd = ("CALC%d:DATA? FDATA" %
                   ch) if formated else ("CALC%d:DATA? SDATA" % ch)
        data = np.asarray(self.query_ascii_values(cmd))
        if formated:
            if self.model in ['E5071C']:
                data = data[::2]
        else:
            data = data[::2] + 1j * data[1::2]
        #Start the sweep
        self.setValue('Sweep', 'ON')
        return data

    def pna_select(self, ch=1):
        '''Select the measurement'''
        if self.model in ['E5071C']:
            return
        if self.model in ['E8363C', 'E8363B']:
            quote = '" '
        elif self.model in ['ZNB20-2Port']:
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
            return np.asarray(self.query_ascii_values(cmd))
        if self.model == 'E8363B':
            freq_star = self.getValue('Frequency start')
            freq_stop = self.getValue('Frequency stop')
            num_of_point = self.getValue('Number of points')
            return np.array(np.linspace(freq_star, freq_stop, num_of_point))
        elif self.model in ['ZNB20-2Port']:
            cmd = 'CALC:DATA:STIM?'
            return np.asarray(self.query_ascii_values(cmd))

    def set_segments(self, segments=[], form='Start Stop'):
        self.write('SENS:SEGM:DEL:ALL')
        if form == 'Start Stop':
            cmd = ['SENS:SEGM:LIST SSTOP,%d' % len(segments)]
            for kw in segments:
                data = '1,%(num)d,%(start)g,%(stop)g,%(IFBW)g,0,%(power)g' % kw
                cmd.append(data)
        else:
            cmd = ['SENS:SEGM:LIST CSPAN,%d' % len(segments)]
            for kw in segments:
                data = '1,%(num)d,%(center)g,%(span)g,%(IFBW)g,0,%(power)g' % kw
                cmd.append(data)
        self.write('FORMAT ASCII')
        self.write(','.join(cmd))
