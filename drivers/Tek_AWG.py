# -*- coding: utf-8 -*-
import numpy as np

from lab.device import BaseDriver, QOption, QReal, QList


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

        QList('WList'),

        QList('SList'),
    ]

    def performOpen(self):
        self.waveform_list = self.get_waveform_list()
        self.sequence_list = self.get_sequence_list()

    def performSetValue(self, quant, value, **kw):
        if quant.name == '':
            return
        else:
            return BaseDriver.performSetValue(self, quant, value, **kw)

    def performGetValue(self, quant, **kw):
        if quant.name == 'WList':
            quant.value = self.waveform_list
            return self.waveform_list
        elif quant.name == 'SList':
            quant.value = self.sequence_list
            return self.sequence_list
        else:
            return BaseDriver.performGetValue(self, quant, **kw)

    def get_waveform_list(self):
        if self.model in ['AWG5208']:
            return self.query('WLIS:LIST?').strip("\"\n' ").split(',')
        elif self.model in ['AWG5014C']:
            ret = []
            wlist_size = int(self.query("WLIS:SIZE?"))
            for i in range(wlist_size):
                ret.append(self.query("WLIS:NAME? %d" % (i+1)).strip("\"\n '"))
            return ret
        else:
            return []

    def get_sequence_list(self):
        if self.model in ['AWG5208', 'AWG5014C']:
            ret = []
            slist_size = int(self.query("SLIS:SIZE?"))
            for i in range(slist_size):
                ret.append(self.query("SLIS:NAME? %d" % (i+1)).strip("\"\n '"))
            return ret
        else:
            return []

    def create_waveform(self, name, length, format=None):
        '''
        format: REAL, INT or IQ
        '''
        if name in self.waveform_list:
            return
        if format is None:
            if self.model in ['AWG5208']:
                format = 'REAL'
            else:
                format = 'INT'
        self.write('WLIS:WAV:NEW "%s",%d,%s;' % (name, length, format))
        self.waveform_list.append(name)

    def remove_waveform(self, name):
        if name not in self.waveform_list:
            return
        self.write(':WLIS:WAV:DEL "%s"; *CLS' % name)
        self.waveform_list.remove(name)

    def clear_waveform_list(self):
        wavs_to_delete = self.waveform_list.copy()
        for name in wavs_to_delete:
            self.remove_waveform(name)

    def use_waveform(self, name, ch=1):
        self.write('SOURCE%d:WAVEFORM "%s"' % (ch, name))

    def run_state(self):
        return int(self.query('AWGC:RST?'))

    def run(self):
        self.write('AWGC:RUN')
        self.write('*WAI')

    def stop(self):
        self.write('AWGC:STOP')

    def output_on(self, ch=1):
        self.write('OUTP%d:STAT 1' % ch)

    def output_off(self, ch=1):
        self.write('OUTP%d:STAT 0' % ch)

    def get_current_waveforms(self):
        current_waveforms = []
        current_waveform_size = 0
        for i in [1,2,3,4]:
            wn = self.query('SOUR%d:WAV?' % i)[1:-2]
            current_waveforms.append(wn)
            if wn != '' and current_waveform_size == 0:
                current_waveform_size = self.query_ascii_values('WLIS:WAV:LENGTH? "%s"' % wn, 'd')[0]
        return current_waveform_size, current_waveforms

    def update_waveform(self, points, name='ABS', IQ='I', start=0, size=None):
        w_type = self.query('WLISt:WAVeform:TYPE? "%s"' % name).strip()
        if w_type == 'REAL':
            self._update_waveform_float(points, name, IQ, start, size)
        elif w_type == 'IQ':
            self._update_waveform_float(points[0], name, 'I', start, size)
            self._update_waveform_float(points[1], name, 'Q', start, size)
        else:
            self._update_waveform_int(points, name, start, size)

    def _update_waveform_int(self, points, name='ABS', start=0, size=None):
        """
        points : a 1D numpy.array which values between -1 and 1.
        """
        message = 'WLIST:WAVEFORM:DATA "%s",%d' % (name, start)
        if size is not None:
            message = message + ('%d,' % size)
        points = points.clip(-1,1)
        values = (points * 0x1fff).astype(int) + 0x1fff
        self.write_binary_values(message, values, datatype=u'H',
                                 is_big_endian=False,
                                 termination=None, encoding=None)

    def _update_waveform_float(self, points, name='ABS', IQ='I', start=0, size=None):
        if self.model == 'AWG5208':
            message = 'WLIST:WAVEFORM:DATA:%s "%s",%d,' % (IQ, name, start)
        else:
            message = 'WLIST:WAVEFORM:DATA "%s",%d,' % (name, start)
        if size is not None:
            message = message + ('%d,' % size)
        values = points.clip(-1,1)
        self.write_binary_values(message, values, datatype=u'f',
                                 is_big_endian=False,
                                 termination=None, encoding=None)

    def update_marker(self, name, mk1, mk2=None, mk3=None, mk4=None, start=0, size=None):
        def format_marker_data(markers, bits):
            values = 0
            for i, v in markers:
                v = 0 if v is None else np.asarray(v)
                values += v << bits[i]
            return values

        if self.model in ['AWG5014C']:
            values = format_marker_data([mk1, mk2], [5,6])
        elif self.model in ['AWG5208']:
            values = format_marker_data([mk1, mk2, mk3, mk4], [7,6,5,4])
        if size is None:
            message = 'WLIST:WAVEFORM:MARKER:DATA "%s",%d,' % (name, start)
        else:
            message = 'WLIST:WAVEFORM:MARKER:DATA "%s",%d,%d,' % (name, start, size)
        self.write_binary_values(message, values, datatype=u'B',
                                 is_big_endian=False,
                                 termination=None, encoding=None)

    def create_sequence(self, name, steps, tracks):
        if name in self.sequence_list:
            return
        self.write('SLIS:SEQ:NEW "%s", %d, %d' % (name, steps, tracks))
        self.sequence_list.append(name)

    def remove_sequence(self, name):
        if name not in self.sequence_list:
            return
        self.write('SLIS:SEQ:DEL "%s"' % name)
        self.sequence_list.remove(name)

    def clear_sequence_list(self):
        self.write('SLIS:SEQ:DEL ALL')
        self.sequence_list.clear()

    def set_sequence_step(self, name, sub_name, step, wait='OFF', goto='NEXT', repeat=1, jump=None):
        """set a step of sequence

        name: sequence name
        sub_name: subsequence name or list of waveforms for every tracks
        wait: ATRigger | BTRigger | ITRigger | OFF
        goto: <NR1> | LAST | FIRSt | NEXT | END
        repeat: ONCE | INFinite | <NR1>
        jump: a tuple (jump_input, jump_to)
            jump_input: ATRigger | BTRigger | OFF | ITRigger
            jump_to: <NR1> | NEXT | FIRSt | LAST | END
        """
        if isinstance(sub_name, str):
            self.write('SLIS:SEQ:STEP%d:TASS:SEQ "%s","%s"' % (step, name, sub_name))
        else:
            for i, wav in enumerate(sub_name):
                self.write('SLIS:SEQ:STEP%d:TASS%d:WAV "%s","%s"' % (step, i+1, name, wav))
        self.write('SLIS:SEQ:STEP%d:WINP "%s", %s' % (step, name, wait))
        self.write('SLIS:SEQ:STEP%d:GOTO "%s", %s' % (step, name, goto))
        self.write('SLIS:SEQ:STEP%d:RCO "%s", %s' % (step, name, repeat))
        if jump is not None:
            self.write('SLIS:SEQ:STEP%d:EJIN "%s", %s' % (step, name, jump[0]))
            self.write('SLIS:SEQ:STEP%d:EJUM "%s", %s' % (step, name, jump[1]))

    def use_sequence(self, name, channels=[1,2]):
        for i, ch in enumerate(channels):
            self.write('SOUR%d:CASS:SEQ "%s", %d' % (ch, name, i+1))
