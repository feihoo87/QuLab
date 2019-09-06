import logging
import time

import numpy as np
import re

from qulab.Driver import BaseDriver

from .AlazarTechWrapper import (AlazarTechDigitizer, AutoDMA, DMABufferArray,
                                configure,initialize)
from .exception import AlazarTechError

log = logging.getLogger('qulab.Driver')


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
    def __init__(self, addr=None, **kw):
        super().__init__(addr=addr,**kw)

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
                           recordsPerBuffer=64,
                           bufferCount=512)
        self.config['e'] = getExpArray(self.config['f_list'], self.config['n'],
                                       self.config['weight'],
                                       self.config['sampleRate'])
        self.config['samplesPerRecord'] = getSamplesPerRecode(self.config['n'])

    def performOpen(self):
        if self.addr is not None:
            dict_parse=self._parse_addr(self.addr)
        else:
            dict_parse={}
        self.model=dict_parse.get('model',None)
        systemID=dict_parse.get('systemID',1) #default 1
        boardID=dict_parse.get('boardID',1) #default 1
        self.handle = AlazarTechDigitizer(systemID, boardID)
        initialize(self.handle)
        configure(self.handle, **self.config)

    def _parse_addr(self,addr):
        ats_addr = re.compile(
            r'^ATS(9360|9850|9870)::SYSTEM([0-9]+)::([0-9]+)(|::INSTR)$')
        # example: ATS9870::SYSTEM1::1
        m = ats_addr.search(addr)
        if m is None:
            raise Error('ATS address error!')
        model = 'ATS'+str(m.group(1)) # ATS 9360|9850|9870
        systemID = int(m.group(2))
        boardID = int(m.group(3))
        return dict(model=model,systemID=systemID,boardID=boardID)

    def set(self, **cmd):
        if 'n' in cmd:
            cmd['samplesPerRecord'] = getSamplesPerRecode(cmd['n'])

        self.config.update(cmd)

        if self.config['repeats'] % self.config['recordsPerBuffer'] != 0:
            self.config['repeats'] = (
                self.config['repeats'] // self.config['recordsPerBuffer'] +
                1) * self.config['recordsPerBuffer']

        if any(key in ['f_list', 'n', 'weight', 'sampleRate'] for key in cmd):
            self.config['e'] = getExpArray(self.config['f_list'],
                                           self.config['n'],
                                           self.config['weight'],
                                           self.config['sampleRate'])

        if any(key in [
                'ARange', 'BRange', 'trigLevel', 'triggerDelay',
                'triggerTimeout','bufferCount',
        ] for key in cmd):
            configure(self.handle, **self.config)

    def setValue(self, name, value):
        self.set(**{name: value})

    def getValue(self, name):
        return self.config.get(name, None)

    def _aquireData(self, samplesPerRecord, repeats, buffers, recordsPerBuffer,
                    timeout):
        with AutoDMA(self.handle,
                     samplesPerRecord,
                     repeats=repeats,
                     buffers=buffers,
                     recordsPerBuffer=recordsPerBuffer,
                     timeout=timeout) as h:
            yield from h.read()

    def getData(self, fft=False, avg=False):
        samplesPerRecord = self.config['samplesPerRecord']
        recordsPerBuffer = self.config['recordsPerBuffer']
        repeats = self.config['repeats']
        e = self.config['e']
        n = e.shape[0]
        maxlen = self.config['maxlen']

        A, B = None, None

        retry = 0
        while retry < 3:
            try:
                for chA, chB in self._aquireData(
                        samplesPerRecord,
                        repeats=repeats,
                        buffers=None,
                        recordsPerBuffer=recordsPerBuffer,
                        timeout=1):
                    A_lst = chA.reshape((recordsPerBuffer, samplesPerRecord))
                    B_lst = chB.reshape((recordsPerBuffer, samplesPerRecord))
                    if fft:
                        A_lst = (A_lst[:, :n]).dot(e) / n
                        B_lst = (B_lst[:, :n]).dot(e) / n
                    try:
                        A = np.r_[A, A_lst]
                        B = np.r_[B, B_lst]
                    except:
                        A, B = A_lst, B_lst
                    if repeats == 0 and A.shape[1] >= maxlen:
                        break
                if avg:
                    return A.mean(axis=0), B.mean(axis=0)
                else:
                    return A, B
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
