# -*- coding: utf-8 -*-
import numpy as np
import re
import time
from lab.device import BaseDriver, QInteger, QOption, QReal, QString, QVector


class Driver(BaseDriver):
    error_command = ':SYST:ERR?'
    support_models = ['DSA875']

    quants = [
        QOption('Sweep', value='ON',
            set_cmd='INIT:CONT %(option)s', options=[('OFF', 'OFF'), ('ON', 'ON')]),
        QOption('Trace Mode', value='WRIT',ch=1,
            set_cmd='TRAC%(ch)d:MODE %(option)s',get_cmd='TRAC%(ch)d:MODE?',
            options=[('Write', 'WRIT'), ('Maxhold', 'MAXH'),('Minhold','MINH'),
            ('View','VIEW'),('Blank','BLAN'),('Videoavg','VID'),('Poweravg','POW')]),

        QReal('Frequency Start', unit='Hz', set_cmd='SENS:FREQ:STAR %(value)e%(unit)s', get_cmd='SENS:FREQ:STAR?'),
        QReal('Frequency Stop', unit='Hz', set_cmd='SENS:FREQ:STOP %(value)e%(unit)s', get_cmd='SENS:FREQ:STOP?'),
        QInteger('Sweep Points',value=601, set_cmd=':SWE:POIN %(value)d',get_cmd=':SWE:POIN?')
    ]

    def get_Trace(self, average=1, ch=1):
        '''Get the Trace Data '''

        points=self.getValue('Sweep Points')
        #Stop the sweep
        self.setValue('Sweep', 'OFF')
        if average==1:
            self.setValue('Trace Mode','Write',ch=ch)
            self.write(':SWE:COUN 1')
        else:
            self.setValue('Trace Mode','Poweravg',ch=ch)
            self.write(':TRAC:AVER:COUN %d' % average)
            self.write(':SWE:COUN %d' % average)
            self.write(':TRAC:AVER:RES')
        #Begin a measurement
        self.write('INIT:IMM')
        self.write('*WAI')
        count=float(self.query('SWE:COUN:CURR?'))
        while  count < average:
            count=float(self.query('SWE:COUN:CURR?'))
            time.sleep(0.01)
        #Get the data
        self.write('FORMAT:BORD NORM')
        self.write('FORMAT ASCII')
        data_raw = self.query("TRAC:DATA? TRACE%d" % ch)
        _data = re.split(r", | |\n",data_raw)
        data=[]
        for d in _data[1:1+points]:
            data.append(float(d))
        #Start the sweep
        self.setValue('Sweep', 'ON')
        return np.array(data)


    def get_Frequency(self):
        """Return the frequency of DSA measurement"""

        freq_star=self.getValue('Frequency Start')
        freq_stop=self.getValue('Frequency Stop')
        sweep_point=self.getValue('Sweep Points')
        return np.array(np.linspace(freq_star,freq_stop,sweep_point))

    def get_SNR(self,signalfreqlist=[],signalbandwidth=10e6,average=1, ch=1):
        '''get SNR_dB '''

        Frequency=self.get_Frequency()
        Spectrum=self.get_Trace(average=average, ch=ch)
        Total_power=sum(np.exp(Spectrum/10*np.log(10)))
        Signal_power=0
        #Total_dB=sum(Spectrum)
        #Signal_dB=0
        for sf in signalfreqlist:
            for f in Frequency :
                if f > (sf-signalbandwidth/2) and f < (sf+signalbandwidth/2):
                    index = np.where(Frequency==f)
                    Signal_power = Signal_power + np.exp(Spectrum[index]/10*np.log(10))
                    #Signal_dB = Signal_dB + Spectrum[index]
        _SNR=Signal_power/(Total_power-Signal_power)
        #_SNR=Signal_dB/(Total_dB-Signal_dB)
        SNR = 10*np.log10(_SNR)
        return SNR
