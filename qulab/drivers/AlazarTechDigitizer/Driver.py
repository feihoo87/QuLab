import time

import numpy as np
from qulab import BaseDriver

from .AlazarTechWrapper import (AlazarTechDigitizer, AutoDMA, DMABufferArray,
                                configure)
from .exception import AlazarTechError


def getSamplesPerRecode(numOfPoints):
    samplesPerRecord = 1
    while samplesPerRecord < numOfPoints:
        samplesPerRecord <<= 1
    return samplesPerRecord


def getExpArray(f_list, numOfPoints, sampleRate=1e9):
    e = []
    t = np.arange(0, numOfPoints, 1) / sampleRate
    for f in f_list:
        e.append(np.exp(-1j * 2 * np.pi * f * t))
    return np.asarray(e).T


class Driver(BaseDriver):
    def __init__(self, systemID=1, boardID=1, **kw):
        super().__init__(addr=f'ATS9870::SYS{systemID}::{boardID}::INSTR',
                         model='ATS9870',
                         **kw)
        self.dig = AlazarTechDigitizer(systemID, boardID)
        self.config = dict(n=1024,
                           sampleRate=1e9,
                           f_list=[50e6],
                           repeats=512,
                           maxlen=512,
                           ARange=1.0,
                           BRange=1.0,
                           trigLevel=0.0,
                           triggerDelay=0,
                           triggerTimeout=0,
                           bufferCount=512)
        self.config['e'] = getExpArray(self.config['f_list'], self.config['n'],
                                       self.config['sampleRate'])
        self.config['samplesPerRecord'] = getSamplesPerRecode(self.config['n'])

    def set(self, **cmd):
        if 'n' in cmd:
            cmd['samplesPerRecord'] = getSamplesPerRecode(cmd['n'])

        self.config.update(cmd)

        if any(key in ['f_list', 'n', 'sampleRate'] for key in cmd):
            self.config['e'] = getExpArray(self.config['f_list'],
                                           self.config['n'],
                                           self.config['sampleRate'])

        if any(key in [
                'ARange', 'BRange', 'trigLevel', 'triggerDelay',
                'triggerTimeout'
        ] for key in cmd):
            configure(self.dig, **self.config)

    def setValue(self, name, value):
        self.set(**{name: value})

    def getValue(self, name):
        return self.config.get(name, None)

    def _aquireData(self, samplesPerRecord, repeats, buffers, recordsPerBuffer,
                    timeout):
        with AutoDMA(self.dig,
                     samplesPerRecord,
                     repeats=repeats,
                     buffers=buffers,
                     recordsPerBuffer=recordsPerBuffer,
                     timeout=timeout) as h:
            for chA, chB in h.read():
                yield chA, chB

    def getData(self, fft=False, avg=False):
        samplesPerRecord = self.config['samplesPerRecord']
        repeats = self.config['repeats']
        e = self.config['e']
        maxlen = repeats if repeats > 0 else self.config['maxlen']
        queue = deque(maxlen=maxlen)
        n = e.shape[0]

        while True:
            try:
                for chA, chB in self._aquireData(samplesPerRecord,
                                                 repeats=repeats,
                                                 buffers=None,
                                                 recordsPerBuffer=1,
                                                 timeout=1):
                    if fft:
                        queue.append([chA[:n].dot(e).T / n, chB[:n].dot(e).T / n])
                    else:
                        queue.append([chA[:n], chB[:n]])
                    if len(queue) >= queue.maxlen:
                        break
                if avg:
                    return np.mean(np.asanyarray(queue), axis=0)
                else:
                    return np.asanyarray(queue)
            except AlazarTechError as err:
                print('\n', err)
                if err.code == 518:
                    raise SystemExit(2)
                else:
                    pass
            time.sleep(0.1)

    def getIQ(self, avg=False):
        return self.getData(True, avg)

    def getTraces(self, avg=True):
        return self.getData(False, avg)
