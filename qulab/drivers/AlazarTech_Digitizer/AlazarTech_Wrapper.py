import time
import os
from ctypes import (POINTER, Structure, byref, c_char_p, c_float, c_int,
                    c_int8, c_int16, c_int32, c_int64, c_long, c_uint, c_uint8,
                    c_uint16, c_uint32, c_uint64, c_ulong, c_void_p, c_wchar_p, windll)

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

# refer to labber-drivers AlazarTech_Digitizer_Wrapper
class DMABuffer:
    """"Buffer for DMA"""
    def __init__(self, c_sample_type, size_bytes):
        self.size_bytes = size_bytes

        npSampleType = {
            c_uint8: np.uint8,
            c_uint16: np.uint16,
            c_uint32: np.uint32,
            c_int32: np.int32,
            c_float: np.float32
        }.get(c_sample_type, 0)

        bytes_per_sample = {
            c_uint8:  1,
            c_uint16: 2,
            c_uint32: 4,
            c_int32:  4,
            c_float:  4
        }.get(c_sample_type, 0)

        self.addr = None
        if os.name == 'nt':
            MEM_COMMIT = 0x1000
            PAGE_READWRITE = 0x4
            windll.kernel32.VirtualAlloc.argtypes = [c_void_p, c_long, c_long, c_long]
            windll.kernel32.VirtualAlloc.restype = c_void_p
            self.addr = windll.kernel32.VirtualAlloc(
                0, c_long(size_bytes), MEM_COMMIT, PAGE_READWRITE)
        # elif os.name == 'posix':
        #     libc.valloc.argtypes = [c_long]
        #     libc.valloc.restype = c_void_p
        #     self.addr = libc.valloc(size_bytes)
        else:
            raise Exception("Unsupported OS")


        ctypes_array = (c_sample_type *
                        (size_bytes // bytes_per_sample)).from_address(self.addr)
        self.buffer = np.frombuffer(ctypes_array, dtype=npSampleType)
        self.ctypes_buffer = ctypes_array
        pointer, read_only_flag = self.buffer.__array_interface__['data']

    def __exit__(self):
        if os.name == 'nt':
            MEM_RELEASE = 0x8000
            windll.kernel32.VirtualFree.argtypes = [c_void_p, c_long, c_long]
            windll.kernel32.VirtualFree.restype = c_int
            windll.kernel32.VirtualFree(c_void_p(self.addr), 0, MEM_RELEASE);
        # elif os.name == 'posix':
        #     libc.free(self.addr)
        else:
            raise Exception("Unsupported OS")

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
        self.buffers = []
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

    def setLEDOn(self, on=True):
        if on:
            self.callFunc('AlazarSetLED', self.handle, LED_ON)
        else:
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

    def AlazarPostAsyncBuffer(self, pBuffer, size_bytes):
        RETURN_CODE=self.callFunc('AlazarPostAsyncBuffer', self.handle, pBuffer, size_bytes)

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

    def removeBuffersDMA(self):
        """Clear and remove DMA buffers, to release memory"""
        # make sure buffers release memory
        for buf in self.buffers:
            buf.__exit__()
        # remove all
        self.buffers = []

    # 替换原来的get_Traces_DMA函数，使用NPT，即没有预采样, 参数结构保持一致
    def get_Traces_DMA(self, preTriggerSamples=0, postTriggerSamples=1024, repeats=1000,
                       procces=None, timeout=1, sum=False):
        # NPT mode, postTriggerSamples 最好为128的整数倍
        preTriggerSamples=0

        samplesPerRecord = preTriggerSamples+postTriggerSamples
        recordsPerBuffer = 2
        recordsPerAcquisition = repeats*recordsPerBuffer
        _, bitsPerSample = self.AlazarGetChannelInfo()
        bytesPerSample = (bitsPerSample + 7) // 8
        # bit移位，比如12bit采样深度，返回16bit，需要移位4bit，参考说明书SDK-guide-7.2.2 Processing_data
        bitShift = bytesPerSample*8 - bitsPerSample

        dtype = c_uint8 if bytesPerSample == 1 else c_uint16

        codeZero = (1 << (bitsPerSample - 1)) -0.5
        codeRange = (1 << (bitsPerSample - 1)) -0.5
        bytesPerHeader = 0
        bytesPerRecord = bytesPerSample * samplesPerRecord + bytesPerHeader
        bytesPerBuffer = bytesPerRecord * recordsPerBuffer
        # force buffer size to be integer of 256 * 16 = 4096, not sure why
        # bytesPerBufferMem = int(4096 * np.ceil(bytesPerBuffer/4096.))

        scaleA, scaleB = self.dRange[CHANNEL_A]/codeRange, self.dRange[CHANNEL_B]/codeRange

        Buffer = (dtype*(samplesPerRecord*recordsPerBuffer))()

        if procces is None and sum == True:
            A, B = np.zeros(samplesPerRecord), np.zeros(samplesPerRecord)
        else:
            A, B = [], []

        time_out_ms = int(1000*timeout)

        self.AlazarSetRecordSize(preTriggerSamples, postTriggerSamples)
        self.AlazarSetRecordCount(recordsPerAcquisition)
        self.removeBuffersDMA()
        self.buffers = []
        for i in range(repeats):
            self.buffers.append(DMABuffer(dtype, bytesPerBuffer))

        # Configure the board to make a Traditional AutoDMA acquisition
        self.AlazarBeforeAsyncRead(CHANNEL_A | CHANNEL_B,
                              -preTriggerSamples,
                              samplesPerRecord,
                              recordsPerBuffer,
                              recordsPerAcquisition,
                              ADMA_EXTERNAL_STARTCAPTURE | ADMA_NPT | ADMA_INTERLEAVE_SAMPLES)
        # Post DMA buffers to board
        for buf in self.buffers:
            self.AlazarPostAsyncBuffer(buf.addr, buf.size_bytes)
        try:
            self.AlazarStartCapture()
        except:
            # make sure buffers release memory if failed
            self.removeBuffersDMA()
            raise

        try:
            for i in range(repeats):
                # Wait for the buffer at the head of the list of available
                # buffers to be filled by the board.
                buf = self.buffers[i]
                self.AlazarWaitAsyncBufferComplete(buf.addr, timeout_ms=time_out_ms)
                self.AlazarPostAsyncBuffer(buf.addr, buf.size_bytes)
                self.check_errors(ignores=[RETURN_CODE.ApiTransferComplete])

                buf_truncated = buf.buffer
                _data = buf_truncated >> bitShift
                # 两个通道数据交替，所以需要reshape
                data = np.array(_data, dtype=np.float).reshape((samplesPerRecord,2))
                data -= codeZero
                ch1 = scaleA * data[:,0]
                ch2 = scaleB * data[:,1]
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
            # release resources
            try:
                self.AlazarAbortAsyncRead()
            except:
                pass

        return A, B


    def get_Traces_DMA_old(self, preTriggerSamples=0, postTriggerSamples=1024, repeats=1000,
                       procces=None, timeout=1, sum=False):
        samplesPerRecord = preTriggerSamples+postTriggerSamples
        recordsPerBuffer = 2
        recordsPerAcquisition = repeats*2
        _, bitsPerSample = self.AlazarGetChannelInfo()
        bytesPerSample = (bitsPerSample + 7) // 8
        # bit移位，比如12bit采样深度，返回16bit，需要移位4bit，参考说明书SDK-guide-7.2.2 Processing_data
        bitShift = bytesPerSample*8 - bitsPerSample

        dtype = c_uint8 if bytesPerSample == 1 else c_uint16

        uFlags = ADMA_TRADITIONAL_MODE | ADMA_ALLOC_BUFFERS | ADMA_EXTERNAL_STARTCAPTURE
        codeZero = (1 << (bitsPerSample - 1)) - 0.5
        codeRange = (1 << (bitsPerSample - 1)) - 0.5
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
        self.AlazarSetRecordSize(preTriggerSamples, postTriggerSamples)
        self.AlazarBeforeAsyncRead(CHANNEL_A | CHANNEL_B,
                                   -preTriggerSamples, samplesPerRecord, recordsPerBuffer//2,
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
                # _Buffer = Buffer >> bitShift
                _Buffer = Buffer
                data = np.array(_Buffer, dtype=np.float)
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
