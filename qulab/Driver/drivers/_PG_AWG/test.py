# -*- coding: utf-8 -*-
"""
Created on Sat May 18 13:57:33 2019

@author: csrc
"""

import lab
#import AWGboard, Waveform
import Waveform, AWGboard

awg = AWGboard.AWGBoard()
awg.connect('192.168.1.23')
awg.InitBoard()
awg.display_AWG()