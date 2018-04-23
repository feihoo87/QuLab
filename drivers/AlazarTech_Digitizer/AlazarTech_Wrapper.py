import time
from ctypes import (POINTER, Structure, byref, c_char_p, c_float, c_int,
                    c_int8, c_int16, c_int64, c_long, c_uint, c_uint8,
                    c_uint16, c_uint64, c_ulong, c_void_p, c_wchar_p)

import numpy as np

from . import AlazarApi as API
from .AlazarCmd import *
from .AlazarError import RETURN_CODE

c_long_p = POINTER(c_long)
c_ulong_p = POINTER(c_ulong)
c_int_p = POINTER(c_int)
# AUTODMA Related Routines
#
# Control Flags for AutoDMA used in AlazarStartAutoDMA
ADMA_EXTERNAL_STARTCAPTURE = 0x00000001
ADMA_ENABLE_RECORD_HEADERS = 0x00000008
ADMA_SINGLE_DMA_CHANNEL = 0x00000010
ADMA_ALLOC_BUFFERS = 0x00000020
ADMA_TRADITIONAL_MODE = 0x00000000
ADMA_CONTINUOUS_MODE = 0x00000100
ADMA_NPT = 0x00000200
ADMA_TRIGGERED_STREAMING = 0x00000400
ADMA_FIFO_ONLY_STREAMING = 0x00000800  # ATS9462 mode
ADMA_INTERLEAVE_SAMPLES = 0x00001000
ADMA_GET_PROCESSED_DATA = 0x00002000

inputConv = {
    INPUT_RANGE_PM_20_MV: 0.02,
    INPUT_RANGE_PM_40_MV: 0.04,
    INPUT_RANGE_PM_50_MV: 0.05,
    INPUT_RANGE_PM_80_MV: 0.08,
    INPUT_RANGE_PM_100_MV: 0.1,
    INPUT_RANGE_PM_200_MV: 0.2,
    INPUT_RANGE_PM_400_MV: 0.4,
    INPUT_RANGE_PM_500_MV: 0.5,
    INPUT_RANGE_PM_800_MV: 0.8,
    INPUT_RANGE_PM_1_V: 1.0,
    INPUT_RANGE_PM_2_V: 2.0,
    INPUT_RANGE_PM_4_V: 4.0,
    INPUT_RANGE_PM_5_V: 5.0,
    INPUT_RANGE_PM_8_V: 8.0,
    INPUT_RANGE_PM_10_V: 10.0,
    INPUT_RANGE_PM_20_V: 20.0,
    INPUT_RANGE_PM_40_V: 40.0,
    INPUT_RANGE_PM_16_V: 16.0,
    # INPUT_RANGE_HIFI	=	0x00000020
    INPUT_RANGE_PM_1_V_25: 1.25,
    INPUT_RANGE_PM_2_V_5: 2.5,
    INPUT_RANGE_PM_125_MV: 0.125,
    INPUT_RANGE_PM_250_MV: 0.25
}

def getInputRange(maxInput, model, impedance='50 Ohm', returnNum=False):
    if model in ['ATS9325', 'ATS9350', 'ATS9850', 'ATS9870']:
        available = [
            INPUT_RANGE_PM_40_MV, INPUT_RANGE_PM_100_MV, INPUT_RANGE_PM_200_MV,
            INPUT_RANGE_PM_400_MV, INPUT_RANGE_PM_1_V, INPUT_RANGE_PM_2_V,
            INPUT_RANGE_PM_4_V
        ]
    elif model in ['ATS9351', 'ATS9360']:
        available = [INPUT_RANGE_PM_400_MV]

    for k in available:
        if inputConv[k] >= maxInput:
            ret = k
            break
    else:
        ret = available[-1]
    if returnNum:
        ret = inputConv[ret]

    return ret


class AlazarTechError(Exception):
    def __init__(self, code, msg):
        super(AlazarTechError, self).__init__(msg)
        self.code = code
        self.msg = msg


class AlazarTechDigitizer():
    def __init__(self, systemId=1, boardId=1):
        """The init case defines a session ID, used to identify the instrument"""
        # range settings
        self.dRange = {}
        #print('Number of systems:', API.AlazarNumOfSystems())
        handle = API.AlazarGetBoardBySystemID(systemId, boardId)
        if handle is None:
            raise AlazarTechError(
                -1, 'Device with system ID=%d and board ID=%d could not be found.' % (systemId, boardId))
        self.handle = handle
        self._error_list = []
        self.MemorySizeInSamples, self.BitsPerSample = self.AlazarGetChannelInfo()

    def callFunc(self, sFunc, *args, **kw):
        """General function caller with restype=status, also checks for errors"""
        # get function from Lib
        func = getattr(API, sFunc)
        # call function
        status = func(*args)
        if status != RETURN_CODE.ApiSuccess:
            self._error_list.append((status, "Error '%s' happens when calling function '%s'" % (
                self.getError(status), sFunc)))
        return status

    def errors(self):
        ret = []
        try:
            while True:
                e = self._error_list.pop(0)
                ret.append(e)
        except IndexError:
            return ret
        return []

    def check_errors(self, ignores=[]):
        errors = self.errors()
        for e in errors:
            if e[0] in ignores:
                errors.remove(e)
        if len(errors) != 0:
            self.push_back_errors(errors)
            raise AlazarTechError(errors[-1][0], '%d, %s' % errors[-1])

    def push_back_errors(self, e):
        self._error_list.extend(e)

    def AlazarGetChannelInfo(self):
        MemorySizeInSamples, BitsPerSample = API.U32(), API.U8()
        self.callFunc('AlazarGetChannelInfo', self.handle,
                      MemorySizeInSamples, BitsPerSample)
        return MemorySizeInSamples.value, BitsPerSample.value

    def testLED(self):
        import time
        self.callFunc('AlazarSetLED', self.handle, LED_ON)
        time.sleep(0.1)
        self.callFunc('AlazarSetLED', self.handle, LED_OFF)

    def getError(self, status):
        """Convert the error in status to a string"""
        # const char* AlazarErrorToText(RETURN_CODE retCode)
        errorText = API.AlazarErrorToText(status)
        return str(errorText)

    # RETURN_CODE AlazarStartCapture( HANDLE h);
    def AlazarStartCapture(self):
        self.callFunc('AlazarStartCapture', self.handle)

    def AlazarWaitAsyncBufferComplete(self, pBuffer, timeout_ms):
        self.callFunc("AlazarWaitAsyncBufferComplete", self.handle,
                      pBuffer, timeout_ms)

    # RETURN_CODE AlazarAbortCapture( HANDLE h);
    def AlazarAbortCapture(self):
        self.callFunc('AlazarAbortCapture', self.handle)

    # RETURN_CODE AlazarSetCaptureClock( HANDLE h, U32 Source, U32 Rate, U32 Edge, U32 Decimation);
    def AlazarSetCaptureClock(self, SourceId, SampleRateId, EdgeId=0, Decimation=0):
        if SourceId == EXTERNAL_CLOCK_10MHz_REF:
            SampleRateId = 1000000000
            Decimation = 1
        self.callFunc('AlazarSetCaptureClock', self.handle,
                      SourceId, SampleRateId, EdgeId, Decimation)

    # RETURN_CODE AlazarSetTriggerOperation(HANDLE h, U32 TriggerOperation
    #            ,U32 TriggerEngine1/*j,K*/, U32 Source1, U32 Slope1, U32 Level1
    #            ,U32 TriggerEngine2/*j,K*/, U32 Source2, U32 Slope2, U32 Level2);
    def AlazarSetTriggerOperation(self, TriggerOperation=0,
                                  TriggerEngine1=0, Source1=0, Slope1=1, Level1=128,
                                  TriggerEngine2=1, Source2=3, Slope2=1, Level2=128):
        self.callFunc('AlazarSetTriggerOperation', self.handle, TriggerOperation,
                      TriggerEngine1, Source1, Slope1, Level1,
                      TriggerEngine2, Source2, Slope2, Level2)

    # RETURN_CODE  AlazarSetTriggerDelay( HANDLE h, U32 Delay);
    def AlazarSetTriggerDelay(self, Delay=0):
        self.callFunc('AlazarSetTriggerDelay', self.handle, Delay)

    # RETURN_CODE  AlazarSetTriggerTimeOut( HANDLE h, U32 to_ns);
    def AlazarSetTriggerTimeOut(self, time=0.0):
        tick = int(time*1E5)
        self.callFunc('AlazarSetTriggerTimeOut', self.handle, tick)

    # RETURN_CODE AlazarSetBWLimit( HANDLE h, U8 Channel, U32 enable);
    def AlazarSetBWLimit(self, Channel, enable):
        self.callFunc('AlazarSetBWLimit', self.handle, Channel, enable)

    # RETURN_CODE AlazarSetRecordSize( HANDLE h, U32 PreSize, U32 PostSize);
    def AlazarSetRecordSize(self, PreSize, PostSize):
        self.nPreSize = int(PreSize)
        self.nPostSize = int(PostSize)
        self.callFunc('AlazarSetRecordSize', self.handle, PreSize, PostSize)

    # RETURN_CODE AlazarSetRecordCount( HANDLE h, U32 Count);
    def AlazarSetRecordCount(self, Count):
        self.nRecord = int(Count)
        self.callFunc('AlazarSetRecordCount', self.handle, Count)

    # U32	AlazarBusy( HANDLE h);
    def AlazarBusy(self):
        # call function, return result
        return bool(API.AlazarBusy(self.handle))

    def AlazarRead(self, Channel, Buffer, ElementSize, Record, TransferOffset, TransferLength):
        self.callFunc('AlazarRead', self.handle,
                      Channel, Buffer, ElementSize,
                      Record, TransferOffset, TransferLength)

    # RETURN_CODE AlazarInputControl( HANDLE h, U8 Channel, U32 Coupling, U32 InputRange, U32 Impedance);
    def AlazarInputControl(self, Channel, Coupling, InputRange, Impedance):
        # keep track of input range
        self.dRange[Channel] = inputConv[InputRange]
        self.callFunc('AlazarInputControl', self.handle,
                      Channel, Coupling, InputRange, Impedance)

    # RETURN_CODE AlazarSetExternalTrigger( HANDLE h, U32 Coupling, U32 Range);
    def AlazarSetExternalTrigger(self, Coupling, Range=0):
        self.callFunc('AlazarSetExternalTrigger', self.handle, Coupling, Range)

    def AlazarBeforeAsyncRead(self, channelMask,         # U32 -- enabled channal mask
                              preTriggerSamples,         # long -- trigger offset
                              samplesPerRecord,          # U32 -- samples per record
                              recordsPerBuffer,          # U32 -- records per buffer
                              recordsPerAcquisition,     # U32 -- records per acquisition
                              flags):                    # U32 -- AutoDMA mode and options
        self.callFunc("AlazarBeforeAsyncRead", self.handle,
                      channelMask, preTriggerSamples,
                      samplesPerRecord, recordsPerBuffer,
                      recordsPerAcquisition, flags)

    def AlazarWaitNextAsyncBufferComplete(self,
                                          pBuffer,  # void* -- buffer to receive data
                                          bytesToCopy,  # U32 -- bytes to copy into buffer
                                          timeout_ms):  # U32 -- time to wait for buffer):
        self.callFunc("AlazarWaitNextAsyncBufferComplete", self.handle,
                      pBuffer, bytesToCopy, timeout_ms)

    def AlazarAbortAsyncRead(self):
        self.callFunc('AlazarAbortAsyncRead', self.handle)

    def AlazarSetParameter(self, ChannelId, ParameterId, Value):
        self.callFunc('AlazarSetParameter', self.handle,
                      ChannelId, ParameterId, Value)

    def AlazarGetParameter(self, ChannelId, ParameterId):
        Value = API.c_long()
        self.callFunc('AlazarGetParameter', self.handle,
                      ChannelId, ParameterId, Value)
        return Value.value

    def get_Traces_DMA(self, preTriggerSamples=0, postTriggerSamples=1024, repeats=1000,
                       procces=None, timeout=1, sum=False):
        samplesPerRecord = preTriggerSamples+postTriggerSamples
        recordsPerBuffer = 2
        recordsPerAcquisition = repeats*2
        _, bitsPerSample = self.AlazarGetChannelInfo()
        bytesPerSample = (bitsPerSample + 7) // 8

        dtype = c_uint8 if bytesPerSample == 1 else c_uint16

        uFlags = ADMA_TRADITIONAL_MODE | ADMA_ALLOC_BUFFERS | ADMA_EXTERNAL_STARTCAPTURE
        codeZero = 1 << (bitsPerSample - 1)
        codeRange = 1 << (bitsPerSample - 1)
        bytesPerHeader = 0
        bytesPerRecord = bytesPerSample * samplesPerRecord + bytesPerHeader
        bytesPerBuffer = bytesPerRecord * recordsPerBuffer
        scaleA, scaleB = self.dRange[CHANNEL_A]/codeRange, self.dRange[CHANNEL_B]/codeRange

        Buffer = (dtype*(samplesPerRecord*recordsPerBuffer))()

        if procces is None and sum == True:
            A, B = np.zeros(samplesPerRecord), np.zeros(samplesPerRecord)
        else:
            A, B = [], []

        time_out_ms = int(1000*timeout)

        self.AlazarSetParameter(0, SET_DATA_FORMAT, DATA_FORMAT_UNSIGNED)
        self.AlazarBeforeAsyncRead(CHANNEL_A | CHANNEL_B,
                                   -preTriggerSamples, samplesPerRecord, recordsPerBuffer,
                                   recordsPerAcquisition,
                                   uFlags)
        self.check_errors()

        self.AlazarStartCapture()
        self.check_errors()

        try:
            for i in range(repeats):
                self.AlazarWaitNextAsyncBufferComplete(
                    Buffer, bytesPerBuffer, time_out_ms)
                self.check_errors(ignores=[RETURN_CODE.ApiTransferComplete])
                data = np.array(Buffer, dtype=np.float)
                data -= codeZero
                ch1, ch2 = scaleA * data[:samplesPerRecord],\
                           scaleB * data[samplesPerRecord:]
                if procces is None and sum == False:
                    A.append(ch1[:samplesPerRecord])
                    B.append(ch2[:samplesPerRecord])
                elif procces is None:
                    A += ch1[:samplesPerRecord]
                    B += ch2[:samplesPerRecord]
                else:
                    a, b = procces(ch1[:samplesPerRecord],
                                   ch2[:samplesPerRecord])
                    A.append(a)
                    B.append(b)
        finally:
            self.AlazarAbortAsyncRead()

        return A, B
