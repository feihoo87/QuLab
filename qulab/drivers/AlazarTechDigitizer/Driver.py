import logging
import time
from collections import deque

import numpy as np

from qulab import BaseDriver

from .AlazarTechWrapper import (AlazarTechDigitizer, AutoDMA, DMABufferArray,
                                configure, initialize)
from .exception import AlazarTechError

log = logging.getLogger(__name__)


def getSamplesPerRecode(numOfPoints):
    samplesPerRecord = (numOfPoints // 64) * 64
    if samplesPerRecord < numOfPoints:
        samplesPerRecord += 64
    return samplesPerRecord


def getExpArray(f_list, numOfPoints, weight=None, sampleRate=1e9):
    e = []
    t = np.arange(0, numOfPoints, 1) / sampleRate
    if weight is None:
        weight = np.ones(numOfPoints)
    for f in f_list:
        e.append(weight * np.exp(-1j * 2 * np.pi * f * t))
    return np.asarray(e).T


class Driver(BaseDriver):
    def __init__(self, systemID=1, boardID=1, config=None, **kw):
        super().__init__(**kw)
        self.dig = AlazarTechDigitizer(systemID, boardID)
        self.config = dict(n=1024,
                           sampleRate=1e9,
                           f_list=[50e6],
                           weight=None,
                           repeats=512,
                           maxlen=512,
                           ARange=1.0,
                           BRange=1.0,
                           trigLevel=0.0,
                           triggerDelay=0,
                           triggerTimeout=0,
                           bufferCount=512)
        self.config['e'] = getExpArray(self.config['f_list'], self.config['n'],
                                       self.config['weight'],
                                       self.config['sampleRate'])
        self.config['samplesPerRecord'] = getSamplesPerRecode(self.config['n'])
        if config is not None:
            self.set(**config)
        initialize(self.dig)
        configure(self.dig, **self.config)

    def set(self, **cmd):
        if 'n' in cmd:
            cmd['samplesPerRecord'] = getSamplesPerRecode(cmd['n'])

        self.config.update(cmd)

        if any(key in ['f_list', 'n', 'weight', 'sampleRate'] for key in cmd):
            self.config['e'] = getExpArray(self.config['f_list'],
                                           self.config['n'],
                                           self.config['weight'],
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
            yield from h.read()

    def getData(self, fft=False, avg=False):
        samplesPerRecord = self.config['samplesPerRecord']
        repeats = self.config['repeats']
        e = self.config['e']
        maxlen = repeats if repeats > 0 else self.config['maxlen']
        queue = deque(maxlen=maxlen)
        n = e.shape[0]

        retry = 0
        while retry < 3:
            try:
                for chA, chB in self._aquireData(samplesPerRecord,
                                                 repeats=repeats,
                                                 buffers=None,
                                                 recordsPerBuffer=1,
                                                 timeout=1):
                    if fft:
                        queue.append(
                            [chA[:n].dot(e).T / n, chB[:n].dot(e).T / n])
                    else:
                        queue.append([chA[:n], chB[:n]])
                    if len(queue) >= queue.maxlen:
                        break
                if avg:
                    return np.mean(np.asanyarray(queue), axis=0)
                else:
                    ret = np.asanyarray(queue)
                    return np.asarray([ret[:, 0, :], ret[:, 1, :]])
            except AlazarTechError as err:
                log.exception(err.msg)
                if err.code == 518:
                    raise SystemExit(2)
                else:
                    pass
            time.sleep(0.1)
            retry += 1
        else:
            raise SystemExit(1)

    def getIQ(self, avg=False):
        return self.getData(True, avg)

    def getTraces(self, avg=True):
        return self.getData(False, avg)
