# -*- coding: utf-8 -*-
import numpy as np

from lab.device import BaseDriver, QInteger, QOption, QReal, QString, QVector


class Driver(BaseDriver):
    support_models = ['AWG5014C', 'AWG5208']

    quants = [
        QReal('Sample Rate', unit='S/s',
          set_cmd='SOUR:FREQ %(value)f',
          get_cmd='SOUR:FREQ?'),

        QOption('Run Mode', set_cmd='AWGC:RMOD %(option)s', get_cmd='AWGC:RMOD?',
            options = [
                ('Continuous', 'CONT'),
                ('Triggered',  'TRIG'),
                ('Gated',      'GAT'),
                ('Sequence',   'SEQ')]),

        QOption('Clock Source', set_cmd='AWGC:CLOC:SOUR %(option)s', get_cmd='AWGC:CLOC:SOUR?',
          options = [('Internal', 'INT'), ('External', 'EXT')]),

        QOption('Reference Source', set_cmd='SOUR:ROSC:SOUR %(option)s', get_cmd='SOUR:ROSC:SOUR?',
          options = [('Internal', 'INT'), ('External', 'EXT')]),

        QReal('Vpp', unit='V',
          set_cmd='SOURCE%(channel)d:VOLT %(value)f',
          get_cmd='SOURCE%(channel)d:VOLT?'),

        QReal('Offset', unit='V',
          set_cmd='SOURCE%(channel)d:VOLT:OFFS %(value)f',
          get_cmd='SOURCE%(channel)d:VOLT:OFFS?'),

        QReal('Volt Low', unit='V',
          set_cmd='SOURCE%(channel)d:VOLT:LOW %(value)f',
          get_cmd='SOURCE%(channel)d:VOLT:LOW?'),

        QReal('Volt High', unit='V',
          set_cmd='SOURCE%(channel)d:VOLT:HIGH %(value)f',
          get_cmd='SOURCE%(channel)d:VOLT:HIGH?'),
    ]

    def performOpen(self):
        pass

    def performSetValue(self, quant, value, **kw):
        if quant.name == '':
            return
        else:
            return BaseDriver.performSetValue(self, quant, value, **kw)

    def performGetValue(self, quant, **kw):
        if quant.name == '':
            return ''
        else:
            return BaseDriver.performGetValue(self, quant, **kw)

    def creat_waveform(self, name, length, format='REAL'):
        '''
        format: REAL, INT or IQ
        '''
        self.write('WLIS:WAV:NEW "%s",%d,%s;' % (name, length, format))

    def remove_waveform(self, name):
        self.write(':WLIS:WAV:DEL "%s"; *CLS' % name)

    def use_waveform(self, name, ch=1):
        self.write('SOURCE%d:WAVEFORM "%s"' % (ch, name))

    def run_state(self):
        return int(self.query(':AWGC:RST?'))

    def run(self):
        self.write(':AWGC:RUN;')

    def stop(self):
        self.write(':AWGC:STOP;')

    def output_on(self, ch=1):
        self.write(':OUTP%d:STAT 1;' % ch)

    def output_off(self, ch=1):
        self.write(':OUTP%d:STAT 0;' % ch)

    def get_current_waveforms(self):
        current_waveforms = []
        current_waveform_size = 0
        for i in [1,2,3,4]:
            wn = self.query('SOUR%d:WAV?' % i)[1:-2]
            current_waveforms.append(wn)
            if wn != '' and current_waveform_size == 0:
                current_waveform_size = self.query_ascii_values('WLIS:WAV:LENGTH? "%s"' % wn, 'd')[0]
        return current_waveform_size, current_waveforms

    def update_waveform(self, points, name='ABS', IQ='I', mk1=None, mk2=None):
        w_type = self.query('WLISt:WAVeform:TYPE? "%s"' % name).strip()
        if w_type == 'REAL':
            self._update_waveform_float(points, name, IQ)
        elif w_type == 'IQ':
            self._update_waveform_float(points[0], name, 'I')
            self._update_waveform_float(points[1], name, 'Q')
        else:
            self._update_waveform_int(points, name, mk1, mk2)

    def _update_waveform_int(self, points, name='ABS', mk1=None, mk2=None):
        """
        points : a 1D numpy.array which values between -1 and 1.
        mk1, mk2: a string contain only '0' and '1'.
        """
        message = 'WLIST:WAVEFORM:DATA "%s",' % name
        points = points.clip(-1,1)
        values = (points * 0x1fff).astype(int) + 0x1fff
        if mk1 is not None:
            for i in range(min(len(mk1), len(values))):
                if mk1[i] == '1':
                    values[i] = values[i] + 0x4000
        if mk2 is not None:
            for i in range(min(len(mk2), len(values))):
                if mk2[i] == '1':
                    values[i] = values[i] + 0x8000
        self.write_binary_values(message, values, datatype=u'H',
                                 is_big_endian=False,
                                 termination=None, encoding=None)

    def _update_waveform_float(self, points, name='ABS', IQ='I'):
        if self.model == 'AWG5208':
            message = 'WLIST:WAVEFORM:DATA:%s "%s",' % (IQ, name)
        else:
            message = 'WLIST:WAVEFORM:DATA "%s",' % name
        values = points.clip(-1,1)
        self.write_binary_values(message, values, datatype=u'f',
                                 is_big_endian=False,
                                 termination=None, encoding=None)

    def update_marker(self, name, mk1, mk2):
        values = []
        for i in range(len(mk1)):
            d = 0
            if mk1[i] == '1':
                d += 64
            if mk2[i] == '1':
                d += 128
            values.append(d)
        message = 'WLIST:WAVEFORM:MARKER:DATA "%s",' % name
        self.write_binary_values(message, values, datatype=u'B',
                                 is_big_endian=False,
                                 termination=None, encoding=None)
