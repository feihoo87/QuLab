import numpy as np

from qulab.sys import VisaDevice, exclude, get, set


class Device(VisaDevice):

    def get_trace_Keysight(self,
                           channel,
                           period=None,
                           returnTime=False,
                           sampleRate=40e9):
        # self.resource.query(":STOP; *OPC?")
        # self.resource.query(":ADER?")
        # self.resource.write(":SINGle")
        self.resource.write(f":WAVeform:SOURce CHAN{channel}")
        data = self.resource.query(":WAVeform:DATA?")
        data = np.array([float(s) for s in data.split(',')[:-1]])
        if period is not None:
            periodPointNum = int(period * sampleRate)
            n = len(data) // periodPointNum
            data = data[:n * periodPointNum].reshape(
                n, periodPointNum).mean(axis=0)
        if returnTime:
            return np.arange(len(data)) / sampleRate, data
        else:
            return data

    def get_trace_Rigol(self,
                        channel,
                        period=None,
                        returnTime=False,
                        sampleRate=40e9):
        (fmt, typ, points, count, xincrement, xorigin, xreference, yincrement,
         yorigin,
         yreference) = self.resource.query(':WAVeform:PREamble?').split(',')
        fmt = int(fmt)
        typ = int(typ)
        points = int(points)
        count = int(count)
        xincrement = float(xincrement)
        xorigin = float(xorigin)
        xreference = float(xreference)
        yincrement = float(yincrement)
        yorigin = int(yorigin)
        yreference = int(yreference)
        self.resource.write(f':WAV:SOUR CHAN{channel}')
        self.resource.write(':WAV:MODE NORMal')
        self.resource.write(':WAV:FORM BYTE')
        data = (np.asarray(
            self.resource.query_binary_values(':WAV:DATA?', datatype='B')) -
                yreference - yorigin) * yincrement
        if period is not None:
            periodPointNum = int(period * sampleRate)
            n = len(data) // periodPointNum
            data = data[:n * periodPointNum].reshape(
                n, periodPointNum).mean(axis=0)
        if returnTime:
            return np.arange(len(data)) / sampleRate, data
        else:
            return data
