# -*- coding: utf-8 -*-
import numpy as np

from qulab import BaseDriver, QList, QOption, QReal


class Driver(BaseDriver):
    support_models = ['AWG70001A', 'AWG70002A']

    quants = [
        # Sample Rate set_cmd is block cmd
        #
        QReal('Sample Rate',
              unit='S/s',
              set_cmd='CLOC:SRAT %(value).10e; *WAI;',
              get_cmd='CLOC:SRAT?'),
        QOption('Run Mode',
                value='CONT',
                ch=1,
                set_cmd='SOUR%(ch)d:RMOD %(option)s',
                get_cmd='SOUR%(ch)d:RMOD?',
                options=[('Continuous', 'CONT'), ('Triggered', 'TRIG'),
                         ('TContinuous', 'TCON')]),
        QOption('Clock Source',
                value='INT',
                set_cmd='CLOC:SOUR %(option)s',
                get_cmd='CLOC:SOUR?',
                options=[('Internal', 'INT'), ('External', 'EXT'),
                         ('Efixed', 'EFIX'), ('Evariable', 'EVAR')]),

        # QOption('Reference Source', set_cmd='SOUR:ROSC:SOUR %(option)s', get_cmd='SOUR:ROSC:SOUR?',
        #   options = [('Internal', 'INT'), ('External', 'EXT')]),
        QReal('Multiplier Rate ',
              value=1,
              set_cmd='CLOC:EREF:MULT %(value)d',
              get_cmd='CLOC:EREF:MULT?'),
        QReal('Divider Rate ',
              value=1,
              set_cmd='CLOC:EREF:DIV %(value)d',
              get_cmd='CLOC:EREF:DIV?'),

        # 以下四种只在 output path 为 Direct 时有效
        # Vpp range: 250-500mVpp
        QReal('Vpp',
              unit='Vpp',
              ch=1,
              set_cmd='SOUR%(ch)d:VOLT %(value)f%(unit)s',
              get_cmd='SOUR%(ch)d:VOLT?'),
        QReal('Offset',
              unit='V',
              ch=1,
              set_cmd='SOUR%(ch)d:VOLT:OFFS %(value)f%(unit)s',
              get_cmd='SOUR%(ch)d:VOLT:OFFS?'),
        QReal('Volt Low',
              unit='V',
              ch=1,
              set_cmd='SOUR%(ch)d:VOLT:LOW %(value)f%(unit)s',
              get_cmd='SOUR%(ch)d:VOLT:LOW?'),
        QReal('Volt High',
              unit='V',
              ch=1,
              set_cmd='SOUR%(ch)d:VOLT:HIGH %(value)f%(unit)s',
              get_cmd='SOUR%(ch)d:VOLT:HIGH?'),

        # output delay in time
        QReal('timeDelay',
              unit='s',
              ch=1,
              set_cmd='SOUR%(ch)d:DEL:ADJ %(value)f%(unit)s',
              get_cmd='SOUR%(ch)d:DEL:ADJ?'),
        # output delay in point
        QReal('timeDelay',
              unit='point',
              ch=1,
              set_cmd='SOUR%(ch)d:DEL:POIN %(value)d',
              get_cmd='SOUR%(ch)d:DELy:POIN?'),
        QOption('Run',
                value='Play',
                set_cmd='AWGC:%(option)s; *WAI;',
                get_cmd='AWGC:RST?',
                options=[('Play', 'RUN'), ('Stop', 'STOP')]),
        QOption('Output',
                ch=1,
                set_cmd='OUTP%(ch)d %(option)s',
                get_cmd='OUTP%(ch)d?',
                options=[('ON', 1), ('OFF', 0), (1, 'ON'), (0, 'OFF')]),
        QList('WList'),
        QList('SList'),

        # INSTrument MODE : AWG or FG
        QOption('instMode',
                value='AWG',
                set_cmd='INST:MODE %(option)s',
                get_cmd='INST:MODE?',
                options=[
                    ('AWG', 'AWG'),
                    ('FG', 'FGEN'),
                ]),
        QOption('FG Type',
                ch=1,
                value='Sin',
                set_cmd='FGEN:CHAN%(ch)d:TYPE %(option)s',
                get_cmd='FGEN:CHAN%(ch)d:TYPE?',
                options=[
                    ('Sin', 'SINE'),
                    ('Square', 'SQU'),
                    ('Triangle', 'TRI'),
                    ('Noise', 'NOIS'),
                    ('DC', 'DC'),
                    ('Gaussian', 'GAUS'),
                    ('ExpRise', 'EXPR'),
                    ('ExpDecay', 'EXPD'),
                    ('None', 'NONE'),
                ]),
        QReal('FG Amplitude',
              ch=1,
              value=0.5,
              unit='V',
              set_cmd='FGEN:CHAN%(ch)d:AMPL:VOLT %(value)f%(unit)s',
              get_cmd='FGEN:CHAN%(ch)d:AMPL:VOLT?'),

        #FG Offset -150mV~150mV, min Unit 1mV
        QReal('FG Offset',
              ch=1,
              value=0,
              unit='V',
              set_cmd='FGEN:CHAN%(ch)d:OFFS %(value)f%(unit)s',
              get_cmd='FGEN:CHAN%(ch)d:OFFS?'),
        QReal('FG Phase',
              ch=1,
              value=0,
              unit='deg',
              set_cmd='FGEN:CHAN%(ch)d:PHAS %(value)f',
              get_cmd='FGEN:CHAN%(ch)d:PHAS?'),
        QReal('FG Frequency',
              ch=1,
              value=1e6,
              unit='Hz',
              set_cmd='FGEN:CHAN%(ch)d:FREQ %(value)f%(unit)s',
              get_cmd='FGEN:CHAN%(ch)d:FREQ?'),
        QReal(
            'FG Period',
            ch=1,
            unit='s',
            # 周期与频率绑定，无法设置周期，但可读
            set_cmd='',
            get_cmd='FGEN:CHAN%(ch)d:PER?'),

        # DC Level Range: –250 mV to 250 mV
        QReal('FG DC',
              ch=1,
              value=0,
              unit='V',
              set_cmd='FGEN:CHAN%(ch)d:DCL %(value)f%(unit)s',
              get_cmd='FGEN:CHAN%(ch)d:DCL?'),
        QReal('FG High',
              ch=1,
              value=0.25,
              unit='V',
              set_cmd='FGEN:CHAN%(ch)d:HIGH %(value)f%(unit)s',
              get_cmd='FGEN:CHAN%(ch)d:HIGH?'),
        QReal('FG Low',
              ch=1,
              value=-0.25,
              unit='V',
              set_cmd='FGEN:CHAN%(ch)d:LOW %(value)f%(unit)s',
              get_cmd='FGEN:CHAN%(ch)d:LOW?'),

        #coupling mode: DIR, DCAM, AC
        QOption('FG Path',
                ch=1,
                value='Direct',
                set_cmd='FGEN:CHAN%(ch)d:PATH %(option)s',
                get_cmd='FGEN:CHAN%(ch)d:PATH?',
                options=[
                    ('Direct', 'DIR'),
                    ('DCAmplified', 'DCAM'),
                    ('AC', 'AC'),
                ]),
    ]

    def performOpen(self):
        self.waveform_list = self.get_waveform_list()
        try:  #没有sequence模块的仪器会产生一个错误
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
        self.write('WLIS:WAV:NEW "%s",%d,%s;*WAI;' % (name, length, format))
        self.waveform_list = self.get_waveform_list()

    def remove_waveform(self, name=None, all=False):
        if all:
            self.write('WLIS:WAV:DEL ALL; *WAI;')
            self.waveform_list.clear()
        elif name not in self.waveform_list:
            return
        else:
            self.write('WLIS:WAV:DEL "%s"; *WAI;' % name)
            self.waveform_list = self.get_waveform_list()

    def get_waveform_length(self, name):
        size = int(self.query('WLIS:WAV:LENGTH? "%s"' % name))
        return size

    def use_waveform(self, name, ch=1, type=None):
        '''type: I or Q'''
        if type is not None:
            self.write('SOUR%d:CASS:WAV "%s",%s' % (ch, name, type))
        else:
            self.write('SOUR%d:CASS:WAV "%s"' % (ch, name))
        self.write('*WAI;')

    # 关于RUN的设置和状态询问，建议使用Quantity：Run的方法
    def run_state(self):
        return int(self.query('AWGC:RST?'))

    def run(self):
        self.write('AWGC:RUN')
        self.write('*WAI')

    def stop(self):
        self.write('AWGC:STOP')

    # 关于Output的设置和状态询问，建议使用Quantity：Output的方法
    def output_on(self, ch=1):
        self.write('OUTP%d:STAT 1' % ch)

    def output_off(self, ch=1):
        self.write('OUTP%d:STAT 0' % ch)

    def get_current_asset(self, ch=1):
        current_type = self.query('SOUR%d:CASS:TYPE?' % ch)
        current_asset = self.query('SOUR%d:CASS?' % ch)
        return current_type, current_asset

    def update_waveform(self, points, name='ABS', IQ='I', start=0, size=None):
        w_type = self.query('WLIS:WAV:TYPE? "%s"' % name).strip()
        if w_type == 'REAL':
            self._update_waveform_float(points, name, IQ, start, size)
        elif w_type == 'IQ':
            self._update_waveform_float(points[0], name, 'I', start, size)
            self._update_waveform_float(points[1], name, 'Q', start, size)
        self.write('*WAI;')
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

    def _update_waveform_float(self,
                               points,
                               name='ABS',
                               IQ='I',
                               start=0,
                               size=None):
        message = 'WLIST:WAVEFORM:DATA:%s "%s",%d,' % (IQ, name, start)
        if size is not None:
            message = message + ('%d,' % size)
        values = points.clip(-1, 1)
        self.write_binary_values(message,
                                 values,
                                 datatype=u'f',
                                 is_big_endian=False,
                                 termination=None,
                                 encoding=None)

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
        self.write('SLIS:SEQ:NEW "%s", %d, %d; *WAI;' % (name, steps, tracks))
        self.sequence_list = self.get_sequence_list()

    def remove_sequence(self, name=None, all=False):
        if all:
            self.write('SLIS:SEQ:DEL ALL; *WAI;')
            self.sequence_list.clear()
        elif name not in self.sequence_list:
            return
        else:
            self.write('SLIS:SEQ:DEL "%s"; *WAI;' % name)
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
            self.write('SOUR%d:CASS:SEQ "%s", %d, %s' %
                       (ch, name, track, type))
        else:
            self.write('SOUR%d:CASS:SEQ "%s", %d' % (ch, name, track))
        self.write('*WAI;')
