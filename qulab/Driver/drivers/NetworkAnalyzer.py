import numpy as np
import logging
log = logging.getLogger(__name__)
from qulab.Driver import visaDriver, QInteger, QOption, QReal, QVector


class Driver(visaDriver):
    __log__=log
    support_models = ['E8363B', 'E8363C', 'E5071C', 'E5080A',
                    'ZNB20-2Port', 'N5232A']

    quants = [
        QReal('Power',
              value=-20,
              unit='dBm',
              set_cmd='SOUR:POW %(value)e%(unit)s',
              get_cmd='SOUR:POW?'),
        # QOption('PowerMode',
        #         value='OFF',
        #         ch=1,
        #         set_cmd='SOUR%(ch)s:POW:MODE %(option)s',
        #         get_cmd='SOUR%(ch)s:POW:MODE?',
        #         options=[('OFF', 'OFF'), ('ON', 'ON')]),
        QReal('Bandwidth',
              value=1000,
              unit='Hz',
              ch=1,
              set_cmd='SENS%(ch)d:BAND %(value)e%(unit)s',
              get_cmd='SENS%(ch)d:BAND?'),
        QReal('Frequency center',
              value=5e9,
              ch=1,
              unit='Hz',
              set_cmd='SENS%(ch)d:FREQ:CENT %(value)e%(unit)s',
              get_cmd='SENS%(ch)d:FREQ:CENT?'),
        QReal('Frequency span',
              value=2e9,
              ch=1,
              unit='Hz',
              set_cmd='SENS%(ch)d:FREQ:SPAN %(value)e%(unit)s',
              get_cmd='SENS%(ch)d:FREQ:SPAN?'),
        QReal('Frequency start',
              value=4e9,
              ch=1,
              unit='Hz',
              set_cmd='SENS%(ch)d:FREQ:STAR %(value)e%(unit)s',
              get_cmd='SENS%(ch)d:FREQ:STAR?'),
        QReal('Frequency stop',
              value=6e9,
              ch=1,
              unit='Hz',
              set_cmd='SENS%(ch)d:FREQ:STOP %(value)e%(unit)s',
              get_cmd='SENS%(ch)d:FREQ:STOP?'),
        QVector('Frequency', unit='Hz', ch=1),
        QVector('Trace', ch=1),
        QVector('S', ch=1),
        QOption('Sweep',
                value='ON',
                set_cmd='INIT:CONT %(option)s',
                options=[('OFF', 'OFF'), ('ON', 'ON')]),
        QInteger('Number of points',
                 value=201,
                 ch=1,
                 unit='',
                 set_cmd='SENS%(ch)d:SWE:POIN %(value)d',
                 get_cmd='SENS%(ch)d:SWE:POIN?'),
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
                ch=1,
                set_cmd='SENS%(ch)d:SWE:TYPE %(option)s',
                get_cmd='SENS%(ch)d:SWE:TYPE?',
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
    def performOpen(self):
        super().performOpen()
        self.set_timeout(15)
        self.pna_select(ch=1)

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
        #self.pna_select(ch)

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
            #self.write('FORMAT ASCII')
            self.write(':FORM:DATA REAL,32')
            cmd = ("CALC%d:DATA? FDATA" %
                   ch) if formated else ("CALC%d:DATA? SDATA" % ch)
        #data = np.asarray(self.query_ascii_values(cmd))
        data = np.asarray(self.query_binary_values(cmd, is_big_endian=True))
        self.write('FORMAT ASCII')
        if formated:
            if self.model in ['E5071C']:
                data = data[::2]
        else:
            data = data[::2] + 1j * data[1::2]
        #Start the sweep
        self.setValue('Sweep', 'ON')
        return data

    def S(self, i=1, j=1, ch=1, mname="MyMeas"):
        self.create_measurement(name=mname, param=f"S{i}{j}", ch=ch)
        self.write('CALC%d:PAR:SEL "%s"' % (ch, mname))
        #Stop the sweep
        self.setValue('Sweep', 'OFF')
        #Begin a measurement
        self.write('INIT:IMM')
        self.write('*WAI')
        #Get the data
        self.write('FORMAT:BORD NORM')
        if self.model in ['E5071C']:
            self.write(':FORM:DATA ASC')
            cmd = ("CALC%d:DATA:SDATA?" % ch)
        else:
            self.write('FORMAT ASCII')
            cmd = ("CALC%d:DATA? SDATA" % ch)
        #Start the sweep
        self.setValue('Sweep', 'ON')

        data = np.asarray(self.query_ascii_values(cmd))
        data = data[::2] + 1j * data[1::2]
        return data

    def get_measurements(self, ch=1):
        if self.model in ['E5071C']:
            return
        if self.model in ['E8363C', 'E8363B', 'E5080A', 'N5232A']:
            quote = '" '
        elif self.model in ['ZNB20-2Port']:
            quote = "' "
        msg = self.query('CALC%d:PAR:CAT?' % ch).strip(quote)
        meas = msg.split(',')
        return meas[::2], meas[1::2]

    def create_measurement(self, name='MyMeas', param='S11', ch=1):
        mname, params = self.get_measurements(ch=ch)
        if name in mname:
            self.write('CALC%d:PAR:DEL "%s"' % (ch, name))
        self.write('CALC%d:PAR:DEF "%s",%s' % (ch, "MyMeas", param))

    def pna_select(self, ch=1):
        '''Select the measurement'''
        if self.model in ['E5071C']:
            return
        mname, params = self.get_measurements(ch=ch)
        measname = mname[0]
        self.write('CALC%d:PAR:SEL "%s"' % (ch, measname))

    def get_Frequency(self, ch=1):
        """Return the frequency of pna measurement"""

        #Select the measurement
        #self.pna_select(ch)
        if self.model in ['E8363C', 'E5080A']:
            cmd = 'CALC%d:X?' % ch
            self.write(':FORM:DATA REAL,32')
            data = self.query_binary_values(cmd, is_big_endian=True)
            # self.write('FORMAT ASCII')
            return np.asarray(data)
        if self.model in ['E8363B', 'N5232A']:
            freq_star = self.getValue('Frequency start', ch=1)
            freq_stop = self.getValue('Frequency stop', ch=1)
            num_of_point = self.getValue('Number of points', ch=1)
            return np.array(np.linspace(freq_star, freq_stop, num_of_point))
        elif self.model in ['ZNB20-2Port']:
            cmd = 'CALC%d:DATA:STIM?' % ch
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
