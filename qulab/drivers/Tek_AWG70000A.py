# -*- coding: utf-8 -*-
import numpy as np

from qulab import BaseDriver, QOption, QReal, QList


class Driver(BaseDriver):
    support_models = ['AWG70001A', 'AWG70002A']

    quants = [
        QReal('Sample Rate', unit='S/s',
          set_cmd='CLOC:SRAT %(value).10e',
          get_cmd='CLOC:SRAT?'),

        QOption('Run Mode', value='CONT', ch=1,
            set_cmd='SOUR%(ch)d:RMOD %(option)s', get_cmd='SOUR%(ch)d:RMOD?',
            options = [
                ('Continuous', 'CONT'),
                ('Triggered',  'TRIG'),
                ('TContinuous','TCON')]),

        QOption('Clock Source', value='INT',
            set_cmd='CLOC:SOUR %(option)s', get_cmd='CLOC:SOUR?',
            options = [('Internal', 'INT'),
                       ('External', 'EXT'),
                       ('Efixed',   'EFIX'),
                       ('Evariable','EVAR')]),

        # QOption('Reference Source', set_cmd='SOUR:ROSC:SOUR %(option)s', get_cmd='SOUR:ROSC:SOUR?',
        #   options = [('Internal', 'INT'), ('External', 'EXT')]),

        QReal('Multiplier Rate ', value=1,
          set_cmd='CLOC:EREF:MULT %(value)d',
          get_cmd='CLOC:EREF:MULT?'),

         QReal('Divider Rate ', value=1,
           set_cmd='CLOC:EREF:DIV %(value)d',
           get_cmd='CLOC:EREF:DIV?'),

        QReal('Amplitude', unit='V', ch=1,
          set_cmd='SOUR%(ch)d:VOLT %(value)f%(unit)s',
          get_cmd='SOUR%(ch)d:VOLT?'),

        QReal('Offset', unit='V', ch=1,
          set_cmd='SOUR%(ch)d:VOLT:OFFS %(value)f%(unit)s',
          get_cmd='SOUR%(ch)d:VOLT:OFFS?'),

        QReal('Volt Low', unit='V', ch=1,
          set_cmd='SOUR%(ch)d:VOLT:LOW %(value)f%(unit)s',
          get_cmd='SOUR%(ch)d:VOLT:LOW?'),

        QReal('Volt High', unit='V', ch=1,
          set_cmd='SOUR%(ch)d:VOLT:HIGH %(value)f%(unit)s',
          get_cmd='SOUR%(ch)d:VOLT:HIGH?'),
        # output delay in time
        QReal('timeDelay', unit='s', ch=1,
          set_cmd='SOUR%(ch)d:DEL:ADJ %(value)f%(unit)s',
          get_cmd='SOUR%(ch)d:DEL:ADJ?'),
        # output delay in point
        QReal('timeDelay', unit='point', ch=1,
          set_cmd='SOUR%(ch)d:DEL:POIN %(value)d',
          get_cmd='SOUR%(ch)d:DELy:POIN?'),


        QOption('Output', ch=1,
            set_cmd='OUTP%(ch)d %(option)d',
            get_cmd='OUTP%(ch)d?',
            options = [('ON', 1), ('OFF', 0),
                       (1,    1), (0,     0)]),

        QList('WList'),

        QList('SList'),
    ]

    def performOpen(self):
        self.waveform_list = self.get_waveform_list()
        try: #没有sequence模块的仪器会产生一个错误
            self.sequence_list = self.get_sequence_list()
        except:
            self.sequence_list = None

    def performSetValue(self, quant, value, **kw):
        if quant.name == '':
            return
        else:
            return BaseDriver.performSetValue(self, quant, value, **kw)

    def performGetValue(self, quant, **kw):
        if quant.name == 'WList':
            self.waveform_list = self.get_waveform_list()
            return self.waveform_list
        elif quant.name == 'SList':
            self.sequence_list = self.get_sequence_list()
            return self.sequence_list
        else:
            return BaseDriver.performGetValue(self, quant, **kw)

    def get_waveform_list(self):
        return self.query('WLIS:LIST?').strip("\"\n' ").split(',')


    def get_sequence_list(self):
        ret = []
        slist_size = int(self.query("SLIS:SIZE?"))
        for i in range(slist_size):
            ret.append(self.query("SLIS:NAME? %d" % i).strip("\"\n '"))
        return ret

    def create_waveform(self, name, length, format='REAL'):
        '''format: REAL or IQ'''
        if name in self.waveform_list:
            return
        self.write('WLIS:WAV:NEW "%s",%d,%s;' % (name, length, format))
        self.waveform_list = self.get_waveform_list()

    def remove_waveform(self, name=None, all=False):
        if all:
            self.write('WLIS:WAV:DEL ALL; *CLS')
            self.waveform_list.clear()
        elif name not in self.waveform_list:
            return
        else:
            self.write('WLIS:WAV:DEL "%s"; *CLS' % name)
            self.waveform_list = self.get_waveform_list()

    def use_waveform(self, name, ch=1, type=None):
        '''type: I or Q'''
        if type is not None:
            self.write('SOUR%d:CASS:WAV "%s",%s' % (ch, name, type))
        else:
            self.write('SOUR%d:CASS:WAV "%s"' % (ch, name))

    def run_state(self):
        return int(self.query('AWGC:RST?'))

    def run(self):
        self.write('AWGC:RUN')
        self.write('*WAI')

    def stop(self):
        self.write('AWGC:STOP')

    def get_current_asset(self, ch=1):
        current_type = self.query('SOUR%d:CASS:TYPE?' % ch)
        current_asset = self.query('SOUR%d:CASS?' % ch)
        return current_type, current_asset

    def update_waveform(self, points, name='ABS', IQ='I', start=0, size=None):
        w_type = self.query('WLISt:WAV:TYPE? "%s"' % name).strip()
        if w_type == 'REAL':
            self._update_waveform_float(points, name, IQ, start, size)
        elif w_type == 'IQ':
            self._update_waveform_float(points[0], name, 'I', start, size)
            self._update_waveform_float(points[1], name, 'Q', start, size)
        # else:
        #     self._update_waveform_int(points, name, start, size)

    # def _update_waveform_int(self, points, name='ABS', start=0, size=None):
    #     """
    #     points : a 1D numpy.array which values between -1 and 1.
    #     """
    #     message = 'WLIST:WAVEFORM:DATA "%s",%d,' % (name, start)
    #     if size is not None:
    #         message = message + ('%d,' % size)
    #     points = points.clip(-1,1)
    #     values = (points * 0x1fff).astype(int) + 0x1fff
    #     self.write_binary_values(message, values, datatype=u'H',
    #                              is_big_endian=False,
    #                              termination=None, encoding=None)

    def _update_waveform_float(self, points, name='ABS', IQ='I', start=0, size=None):
        message = 'WLIST:WAVEFORM:DATA:%s "%s",%d,' % (IQ, name, start)
        if size is not None:
            message = message + ('%d,' % size)
        values = points.clip(-1,1)
        self.write_binary_values(message, values, datatype=u'f',
                                 is_big_endian=False,
                                 termination=None, encoding=None)

    # def update_marker(self, name, mk1, mk2=None, mk3=None, mk4=None, start=0, size=None):
    #     def format_marker_data(markers, bits):
    #         values = 0
    #         for i, v in markers:
    #             v = 0 if v is None else np.asarray(v)
    #             values += v << bits[i]
    #         return values
    #
    #     if self.model in ['AWG5014C']:
    #         values = format_marker_data([mk1, mk2], [5,6])
    #     elif self.model in ['AWG5208']:
    #         values = format_marker_data([mk1, mk2, mk3, mk4], [7,6,5,4])
    #     if size is None:
    #         message = 'WLIST:WAVEFORM:MARKER:DATA "%s",%d,' % (name, start)
    #     else:
    #         message = 'WLIST:WAVEFORM:MARKER:DATA "%s",%d,%d,' % (name, start, size)
    #     self.write_binary_values(message, values, datatype=u'B',
    #                              is_big_endian=False,
    #                              termination=None, encoding=None)

    def create_sequence(self, name, steps, tracks=1):
        if name in self.sequence_list:
            return
        self.write('SLIS:SEQ:NEW "%s", %d, %d' % (name, steps, tracks))
        self.sequence_list = self.get_sequence_list()

    def remove_sequence(self, name=None, all=False):
        if all:
            self.write('SLIS:SEQ:DEL ALL; *CLS')
            self.sequence_list.clear()
        elif name not in self.sequence_list:
            return
        else:
            self.write('SLIS:SEQ:DEL "%s"' % name)
            self.sequence_list = self.get_sequence_list()

    #
    # def set_sequence_step(self, name, sub_name, step, wait='OFF', goto='NEXT', repeat=1, jump=None):
    #     """set a step of sequence
    #
    #     name: sequence name
    #     sub_name: subsequence name or list of waveforms for every tracks
    #     wait: ATRigger | BTRigger | ITRigger | OFF
    #     goto: <NR1> | LAST | FIRSt | NEXT | END
    #     repeat: ONCE | INFinite | <NR1>
    #     jump: a tuple (jump_input, jump_to)
    #         jump_input: ATRigger | BTRigger | OFF | ITRigger
    #         jump_to: <NR1> | NEXT | FIRSt | LAST | END
    #     """
    #     if isinstance(sub_name, str):
    #         self.write('SLIS:SEQ:STEP%d:TASS:SEQ "%s","%s"' % (step, name, sub_name))
    #     else:
    #         for i, wav in enumerate(sub_name):
    #             self.write('SLIS:SEQ:STEP%d:TASS%d:WAV "%s","%s"' % (step, i+1, name, wav))
    #     self.write('SLIS:SEQ:STEP%d:WINP "%s", %s' % (step, name, wait))
    #     self.write('SLIS:SEQ:STEP%d:GOTO "%s", %s' % (step, name, goto))
    #     self.write('SLIS:SEQ:STEP%d:RCO "%s", %s' % (step, name, repeat))
    #     if jump is not None:
    #         self.write('SLIS:SEQ:STEP%d:EJIN "%s", %s' % (step, name, jump[0]))
    #         self.write('SLIS:SEQ:STEP%d:EJUM "%s", %s' % (step, name, jump[1]))

    def use_sequence(self, name, ch=1, track=1, type=None):
        '''type: I or Q'''
        if type is not None:
            self.write('SOUR%d:CASS:SEQ "%s", %d, %s' % (ch, name, track, type))
        else:
            self.write('SOUR%d:CASS:SEQ "%s", %d' % (ch, name, track))
