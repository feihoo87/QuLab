# -*- coding: utf-8 -*-
import numpy as np
import time

from lab.device import BaseDriver
from lab.device import QReal, QOption, QInteger, QString, QVector

class Driver(BaseDriver):
    error_command = ''
    surport_models = ['33120A', '33220A']
    quants = [
        QReal('Frequency', unit='Hz',
          set_cmd='FREQ %(value).11E Hz',
          get_cmd='FREQ?'),
        QReal('Vpp', unit='V',
          set_cmd='VOLT %(value).5E VPP',
          get_cmd='VOLT?'),
        QReal('Offset', unit='V',
          set_cmd='VOLT:OFFS %(value).5E V',
          get_cmd='VOLT:OFFS?'),
        QVector('Waveform', unit='V'),
        QString('Trigger',
          set_cmd='TRIG:SOUR %(value)s',
          get_cmd='TRIG:SOUR?')
    ]

    def performOpen(self):
        self.write('FORM:BORD NORM')
        self.waveform_list = self.query('DATA:CAT?')[1:-1].split('","')
        self.current_waveform = self.query('FUNC:SHAP?')
        if self.current_waveform == 'USER':
            self.current_waveform = self.query('FUNC:USER?')
        self.arb_waveforms = self.query('DATA:NVOL:CAT?')[1:-1].split('","')
        self.trigger_source = self.query('TRIG:SOUR?')
        self.inner_waveform = ["SINC","NEG_RAMP","EXP_RISE","EXP_FALL","CARDIAC"]

        if self.model == '33120A':
            self.max_waveform_size = 16000
            self.trigger_count  = int(float(self.query('BM:NCYC?')))
        elif self.model == '33220A':
            self.max_waveform_size = 16384
            self.trigger_count  = int(float(self.query("BURS:NCYC?")))

    def performSetValue(self, quant, value, **kw):
        if quant.name == 'Waveform':
            if len(value) > self.max_waveform_size:
                value = value[:self.max_waveform_size]
            value = np.array(value)
            vpp  = value.max() - value.min()
            offs = (value.max() + value.min())/2.0
            name = kw['name'] if 'name' in kw.keys() else 'ABS'
            freq = kw['freq'] if 'freq' in kw.keys() else None
            self.update_waveform(2*(value-offs)/vpp, name=name)
            self.use_waveform(name, vpp=vpp, offs=offs, freq=freq)
        else:
            BaseDriver.performSetValue(self, quant, value, **kw)

    def __del_func(self, name):
        if name in self.arb_waveforms:
            if name == self.current_waveform:
                self.DC(0)
            self.write('DATA:DEL %s' % name)
            self.arb_waveforms.remove(name)
            self.waveform_list.remove(name)

    def update_waveform(self, values, name='ABS'):
        if self.model == '33120A':
            clip = lambda x: (2047*x).clip(-2047,2047).astype(int)
        elif self.model == '33220A':
            clip = lambda x: (8191*x).clip(-8191,8191).astype(int)
        values = clip(values)
        self.write_binary_values('DATA:DAC VOLATILE,', values,
                                 datatype='h', is_big_endian=True)
        if len(name) > 8:
            name = name[:8]
        name = name.upper()

        if len(self.arb_waveforms) >= 4:
            for wf in self.arb_waveforms:
                if wf != self.current_waveform:
                    self.__del_func(wf)

        self.write('DATA:COPY %s,VOLATILE' % name)

    def use_waveform(self, name, freq=None, vpp=None, offs=None, ch=1):
        freq_s = ("%.11E" % freq) if freq != None else "DEF"
        vpp_s  = ("%.5E"  % vpp)  if vpp  != None else "DEF"
        offs_s = ("%.5E"  % offs) if offs != None else "DEF"
        name = name.upper()
        if name in self.inner_waveform:
            self.write('APPL:%s %s,%s,%s' % (name, freq_s, vpp_s, offs_s))
        else:
            self.write('FUNC:USER %s' % name)
            self.write('APPL:USER %s,%s,%s' % (freq_s, vpp_s, offs_s))
        if self.trigger_source != 'IMM':
            self.set_trigger(source = self.trigger_source,
                             count  = self.trigger_count)
        self.current_waveform = name
        time.sleep(1)

    def DC(self, v):
        """输出直流电压"""
        self.write('APPL:DC DEF,DEF,%.5E' % v)
        self.current_waveform = 'DC'

    def off(self):
        self.DC(0)

    def set_trigger(self, source='IMM', count=1):
        """设置触发

        source : 触发源，可设为'IMM', 'EXT' 或 'BUS'
        count  : 脉冲串的个数
        """
        if source not in ['IMM', 'EXT', 'BUS']:
            return
        if count < 1 or count > 50000:
            return
        self.trigger_source = source
        self.write("TRIG:SOUR %s" % source)
        self.trigger_count = count
        if count != 1:
            self.write("BM:NCYC %d" % count)
        if source != 'IMM':
            self.write("BM:STAT ON")

    def refresh(self):
        """刷新波形"""
        if self.current_waveform == "DC":
            return
        if self.current_waveform not in self.inner_waveform:
            self.write("FUNC:SHAP USER")
        else:
            self.write("FUNC:SHAP %s" % self.current_waveform)
