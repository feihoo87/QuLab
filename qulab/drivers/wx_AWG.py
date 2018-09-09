# -*- coding: utf-8 -*-
import numpy as np

from qulab import BaseDriver, QOption, QReal, QList


class Driver(BaseDriver):
    support_models = ['AWG5014C', 'AWG5208']

    quants = [
        QReal('Sample Rate', unit='S/s',
          set_cmd=':FREQ:RAST %(value)g',
          get_cmd=':FREQ:RAST?'),

		QReal('Vpp', unit='V',
           set_cmd=':VOLT:LEV:AMPL %(value)f',
           get_cmd=':VOLT:LEV:AMPL?'),
         
        QReal('Offset', unit='V',
           set_cmd=':VOLT:LEV:OFFS %(value)f',
           get_cmd=':VOLT:LEV:OFFS?'),

		Qoption('Output',
			set_cmd=':OUTP %(option)s',
			get_cmd=':OUTP?',
			options=['ON','OFF']),

		QInteger('Select_ch', value=1, unit='',
			set_cmd=':INST:SEL CH%(value)d',
			get_cmd=':INST:SEL?'),

		QInteger('Select_trac', value=1, unit='',
			set_cmd=':TRAC:SEL %(value)d',
			get_cmd=':TRAC:SEL?'),
			
			)
            ]
	
	def reset(self,samplerate):
		#设置采样率
		self.write(':FREQ:RAST %d',%samplerate)
		#设置外部时钟
		self.write(':ROSCillator:SOURce EXTernal')
		#清除原有波形
		self.write(':INST:SEL CH1')
		self.write(':TRAC:DEL:ALL')
		self.write(':INST:SEL CH3')
		self.write(':TRAC:DEL:ALL')
		#将几个通道的设置设为同一个，详见manual
		self.write(':INST:COUPle:STATe ON')
#		self.write(':INIT:CONT OFF')
#		self.write(':TRIG:COUN 1')
#		self.write('enable')
	
	#创建波形文件
	def crwave(self,segment_num,sample_num):
		self.write(':TRAC:DEF %d,%d' %(segment_num,sample_num))

	#在创建好的波形文件中，写入或者更新具体波形
	def upwave(self,message,points,ch=1,trac=1):
		#选择特定channel
		self.write(':INST:SEL CH%d' %ch)
		#选择特定的segment
		self.write(':TRAC:SEL %d' %trac)
		#选择模式为SINGLE，（包括DUPLicate，SINGle等，详见manual）
		self.write(':TRAC:MODE SING' )
		#写入波形数据
		pointslen=len(points)
		message=':TRAC:DATA#%d%d' % (len(str(2*pointslen)), 2*pointslen)
		points = points.clip(-1,1)
        values = (points * 0x1fff).astype(int) + 0x1fff
        self.write_binary_values(message, values, datatype=u'H',
                                 is_big_endian=False,
                                 termination=None, encoding=None)
	
	#运行波形
	def ruwave(self,ch=1,trac=1):
		self.write(':INST:SEL CH%d' %ch)
		self.write(':TRAC:SEL %d' %trac)
		self.write(':OUTP ON')

