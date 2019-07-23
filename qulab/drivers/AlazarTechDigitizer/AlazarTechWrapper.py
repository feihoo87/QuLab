import os
import time
from contextlib import contextmanager
from ctypes import (CDLL, POINTER, Structure, byref, c_char_p, c_float, c_int,
                    c_int8, c_int16, c_int64, c_long, c_uint, c_uint8,
                    c_uint16, c_uint64, c_ulong, c_void_p, c_wchar_p, windll)

import numpy as np

from . import AlazarApi as API
from .exception import AlazarTechError

if os.name == 'posix':
    try:
        libc = CDLL(u'libc.so.6')
    except:
        libc = CDLL(u'libc.dylib')
else:
    libc = None

c_long_p = POINTER(c_long)
c_ulong_p = POINTER(c_ulong)
c_int_p = POINTER(c_int)

inputConv = {
    API.INPUT_RANGE_PM_20_MV: 0.02,
    API.INPUT_RANGE_PM_40_MV: 0.04,
    API.INPUT_RANGE_PM_50_MV: 0.05,
    API.INPUT_RANGE_PM_80_MV: 0.08,
    API.INPUT_RANGE_PM_100_MV: 0.1,
    API.INPUT_RANGE_PM_200_MV: 0.2,
    API.INPUT_RANGE_PM_400_MV: 0.4,
    API.INPUT_RANGE_PM_500_MV: 0.5,
    API.INPUT_RANGE_PM_800_MV: 0.8,
    API.INPUT_RANGE_PM_1_V: 1.0,
    API.INPUT_RANGE_PM_2_V: 2.0,
    API.INPUT_RANGE_PM_4_V: 4.0,
    API.INPUT_RANGE_PM_5_V: 5.0,
    API.INPUT_RANGE_PM_8_V: 8.0,
    API.INPUT_RANGE_PM_10_V: 10.0,
    API.INPUT_RANGE_PM_20_V: 20.0,
    API.INPUT_RANGE_PM_40_V: 40.0,
    API.INPUT_RANGE_PM_16_V: 16.0,
    # API.INPUT_RANGE_HIFI	=	0x00000020
    API.INPUT_RANGE_PM_1_V_25: 1.25,
    API.INPUT_RANGE_PM_2_V_5: 2.5,
    API.INPUT_RANGE_PM_125_MV: 0.125,
    API.INPUT_RANGE_PM_250_MV: 0.25
}


def getInputRange(maxInput, model, impedance='50 Ohm', returnNum=False):
    if model in [API.ATS9325, API.ATS9350, API.ATS9850, API.ATS9870]:
        available = [
            API.INPUT_RANGE_PM_40_MV, API.INPUT_RANGE_PM_100_MV, API.INPUT_RANGE_PM_200_MV,
            API.INPUT_RANGE_PM_400_MV, API.INPUT_RANGE_PM_1_V, API.INPUT_RANGE_PM_2_V,
            API.INPUT_RANGE_PM_4_V
        ]
    elif model in [API.ATS9351, API.ATS9360]:
        available = [API.INPUT_RANGE_PM_400_MV]

    for k in available:
        if inputConv[k] >= maxInput:
            ret = k
            break
    else:
        ret = available[-1]
    if returnNum:
        ret = inputConv[ret]

    return ret


class AlazarTechDigitizer():
    def __init__(self, systemId=1, boardId=1):
        """The init case defines a session ID, used to identify the instrument"""
        # range settings
        self.inputRange = {}
        #print('Number of systems:', API.AlazarNumOfSystems())
        handle = API.AlazarGetBoardBySystemID(systemId, boardId)
        if handle is None:
            raise AlazarTechError(
                -1,
                'Device with system ID=%d and board ID=%d could not be found.'
                % (systemId, boardId))
        self.handle = handle
        self.__error_list = []
        self.memorySizeInSamples, self.bitsPerSample = self.getChannelInfo()
        self.kind = self.getBoardKind()

    def callFunc(self, funcName, *args, **kw):
        """General function caller with restype=status, also checks for errors"""
        # get function from Lib
        func = getattr(API, funcName)
        # call function
        status = func(*args)
        if status != API.ApiSuccess:
            self.__error_list.append(
                (status, "Error '%s' happens when calling function '%s'" %
                 (self.getError(status), funcName)))
        return status

    def errors(self):
        """Return errors and clear error list."""
        ret = []
        try:
            while True:
                e = self.__error_list.pop(0)
                ret.append(e)
        except IndexError:
            return ret
        return []

    def checkErrors(self, ignores=[]):
        errors = self.errors()
        for e in errors:
            if e[0] in ignores:
                errors.remove(e)
        if len(errors) != 0:
            self.__error_list.extend(errors[:-1])
            raise AlazarTechError(errors[-1][0], '%d, %s' % errors[-1])

    def getError(self, status):
        """Convert the error in status to a string
        """
        errorText = API.AlazarErrorToText(status)
        return str(errorText)

    def getChannelInfo(self):
        memorySizeInSamples, bitsPerSample = API.U32(), API.U8()
        self.callFunc('AlazarGetChannelInfo', self.handle, memorySizeInSamples,
                      bitsPerSample)
        return memorySizeInSamples.value, bitsPerSample.value

    def getBoardKind(self):
        ret = API.AlazarGetBoardKind(self.handle)
        return ret

    def setLEDOn(self, on=True):
        if on:
            self.callFunc('AlazarSetLED', self.handle, API.LED_ON)
        else:
            self.callFunc('AlazarSetLED', self.handle, API.LED_OFF)

    def setCaptureClock(self, SourceId, SampleRateId, EdgeId=0, Decimation=0):
        """Configure sample clock source, edge, and decimation.
        """
        if SourceId == API.EXTERNAL_CLOCK_10MHz_REF:
            SampleRateId = 1000000000
            Decimation = 1
        self.callFunc('AlazarSetCaptureClock', self.handle, SourceId,
                      SampleRateId, EdgeId, Decimation)

    def setTriggerOperation(self,
                            TriggerOperation=0,
                            TriggerEngine1=0,
                            Source1=0,
                            Slope1=1,
                            Level1=128,
                            TriggerEngine2=1,
                            Source2=3,
                            Slope2=1,
                            Level2=128):
        """Configure the trigger system.

        In general, the trigger level code is given by:
            TriggerLevelCode = 128 + 127 * TriggerLevelVolts / InputRangeVolts.
        """
        self.callFunc('AlazarSetTriggerOperation', self.handle,
                      TriggerOperation, TriggerEngine1, Source1, Slope1,
                      Level1, TriggerEngine2, Source2, Slope2, Level2)

    def setTriggerDelay(self, Delay=0):
        """Set the time, in sample clocks, to wait after receiving a trigger
        event before capturing a record for the trigger.
        
        To convert the trigger delay from seconds to sample clocks, multiple
        the sample rate in samples per second by the trigger delay in seconds.
        The trigger delay value may be 0 to 9,999,999 samples.
        The trigger delay value must be a multiple of 4 for the ATS850 and
        ATS860.
        The minimum trigger delay for the ATS9350 and ATS9360 is 16 samples
        in single channel mode, or 8 samples in dual channel mode.
        """
        self.callFunc('AlazarSetTriggerDelay', self.handle, Delay)

    def setTriggerTimeOut(self, timeout=0.0):
        """Set the time to wait for a trigger event before automatically
        generating a trigger event.
        
        timeout : Trigger timeout in 1 s units, or 0 to wait forever for
        a trigger event.
        """
        tick = int(timeout * 1E5)
        self.callFunc('AlazarSetTriggerTimeOut', self.handle, tick)

    def setBWLimit(self, Channel, enable):
        self.callFunc('AlazarSetBWLimit', self.handle, Channel, enable)

    def setRecordSize(self, PreSize, PostSize):
        self.preSize = int(PreSize)
        self.postSize = int(PostSize)
        self.callFunc('AlazarSetRecordSize', self.handle, PreSize, PostSize)

    def setRecordCount(self, Count):
        self.recordCount = int(Count)
        self.callFunc('AlazarSetRecordCount', self.handle, Count)

    def inputControl(self, Channel, Coupling, InputRange, Impedance):
        self.inputRange[Channel] = inputConv[InputRange]
        self.callFunc('AlazarInputControl', self.handle, Channel, Coupling,
                      InputRange, Impedance)

    def setExternalTrigger(self, Coupling, Range=0):
        self.callFunc('AlazarSetExternalTrigger', self.handle, Coupling, Range)

    def configureAuxIO(self, Mode, Parameter):
        """Configure the AUX I/O connector as an input or output signal.
        """
        self.callFunc('AlazarConfigureAuxIO', self.handle, Mode, Parameter)

    def setParameter(self, ChannelId, ParameterId, Value):
        self.callFunc('AlazarSetParameter', self.handle, ChannelId,
                      ParameterId, Value)

    def getParameter(self, ChannelId, ParameterId):
        Value = API.c_long()
        self.callFunc('AlazarGetParameter', self.handle, ChannelId,
                      ParameterId, Value)
        return Value.value

    def startCapture(self):
        """Arm a board to start an acquisition.
        """
        self.callFunc('AlazarStartCapture', self.handle)

    def abortCapture(self):
        """Abort an acquisition to on-board memory.
        """
        self.callFunc('AlazarAbortCapture', self.handle)

    def isBusy(self):
        return bool(API.AlazarBusy(self.handle))

    def read(self, Channel, Buffer, ElementSize, Record, TransferOffset,
             TransferLength):
        self.callFunc('AlazarRead', self.handle, Channel, Buffer, ElementSize,
                      Record, TransferOffset, TransferLength)

    def abortAsyncRead(self):
        """Aborts any in-progress DMA transfers, and cancel any pending transfers.
        """
        self.callFunc('AlazarAbortAsyncRead', self.handle)

    def beforeAsyncRead(
            self,
            channelMask,  # U32 -- enabled channal mask
            preTriggerSamples,  # long -- trigger offset
            samplesPerRecord,  # U32 -- samples per record
            recordsPerBuffer,  # U32 -- records per buffer
            recordsPerAcquisition,  # U32 -- records per acquisition
            flags):  # U32 -- AutoDMA mode and options
        self.callFunc("AlazarBeforeAsyncRead", self.handle, channelMask,
                      preTriggerSamples, samplesPerRecord, recordsPerBuffer,
                      recordsPerAcquisition, flags)

    def waitNextAsyncBufferComplete(
            self,
            pBuffer,  # void* -- buffer to receive data
            bytesToCopy,  # U32 -- bytes to copy into buffer
            timeout_ms):  # U32 -- time to wait for buffer):
        """
        This function returns when the board has received sufficient trigger
        events to fill the buffer, or the timeout interval has elapsed.
        To use this function, AlazarBeforeAsyncRead must be called with the
        ADMA_ALLOC_BUFFERS flag.
        """
        self.callFunc("AlazarWaitNextAsyncBufferComplete", self.handle,
                      pBuffer, bytesToCopy, timeout_ms)

    def waitAsyncBufferComplete(self, pBuffer, timeout_ms):
        """Returns when a board has received sufficient triggers to fill the
        specified buffer, or the timeout interval elapses.
        
        pBuffer : Pointer to a buffer to receive sample data from the digitizer
                board.
        timeout_ms : Specify the time to wait, in milliseconds, for the buffer
                to be filled.
        """
        self.callFunc("AlazarWaitAsyncBufferComplete", self.handle, pBuffer,
                      timeout_ms)

    def postAsyncBuffer(self, pBuffer, BufferLength):
        """Add a buffer to the end of a list of buffers available to be filled
        by the board. Use AlazarWaitAsyncBufferComplete to determine if the
        board has received sufficient trigger events to fill this buffer.
        """
        self.callFunc("AlazarPostAsyncBuffer", self.handle, pBuffer,
                      BufferLength)


def initialize(dig):
    dig.setCaptureClock(API.EXTERNAL_CLOCK_10MHz_REF, API.SAMPLE_RATE_1GSPS)
    dig.setBWLimit(API.CHANNEL_A, 0)
    dig.setBWLimit(API.CHANNEL_B, 0)
    dig.setExternalTrigger(API.DC_COUPLING)
    dig.configureAuxIO(API.AUX_OUT_TRIGGER, 0)
    dig.setParameter(0, API.SET_DATA_FORMAT, API.DATA_FORMAT_UNSIGNED)


def configure(
    dig, ARange=1.0, BRange=1.0,
    trigLevel=0.3, triggerDelay=0, triggerTimeout=0,
    bufferCount=1024,
    **kw):
    dig.inputControl(API.CHANNEL_A, API.DC_COUPLING, getInputRange(ARange, dig.kind),
                     API.IMPEDANCE_50_OHM)
    dig.inputControl(API.CHANNEL_B, API.DC_COUPLING, getInputRange(BRange, dig.kind),
                     API.IMPEDANCE_50_OHM)

    # convert relative level to U8
    maxLevel = 5.0
    Level = int(128 + 127 * trigLevel / maxLevel)
    JLevel = Level
    KLevel = Level
    dig.setTriggerOperation(API.TRIG_ENGINE_OP_J, API.TRIG_ENGINE_J, API.TRIG_EXTERNAL,
                            API.TRIGGER_SLOPE_POSITIVE, JLevel, API.TRIG_ENGINE_K,
                            API.TRIG_DISABLE, API.TRIGGER_SLOPE_POSITIVE, KLevel)
    
    dig.setTriggerDelay(triggerDelay)
    dig.setTriggerTimeOut(triggerTimeout)

    dig.setParameter(0, API.SETGET_ASYNC_BUFFCOUNT, bufferCount)


class DMABuffer:
    def __init__(self, dtype, size):
        """
        dtype: c_uint8 | c_uint16
        size: number of samples
        """
        bytesPerSample = {
            c_uint8: 1,
            c_uint16: 2,
        }[dtype]

        self.dtype = dtype
        self.size = size
        self.bytes = size * bytesPerSample

        self.addr = -1
        self.buffer = None
        self.ctypesBuffer = None

    def alloc(self):
        self.addr = self._alloc(self.bytes)
        ctypesArray = (self.dtype * self.size).from_address(self.addr)
        self.buffer = np.frombuffer(
            ctypesArray,
            dtype=np.uint8 if self.dtype == c_uint8 else np.uint16)
        self.ctypesBuffer = ctypesArray

    def free(self):
        self._free(self.addr)

    def _alloc(self, size):
        if os.name == 'nt':
            MEM_COMMIT = 0x1000
            PAGE_READWRITE = 0x4
            windll.kernel32.VirtualAlloc.argtypes = [
                c_void_p, c_long, c_long, c_long
            ]
            windll.kernel32.VirtualAlloc.restype = c_void_p
            addr = windll.kernel32.VirtualAlloc(0, c_long(size), MEM_COMMIT,
                                                PAGE_READWRITE)
        elif os.name == 'posix':
            libc.valloc.argtypes = [c_long]
            libc.valloc.restype = c_void_p
            addr = libc.valloc(size)
        else:
            raise Exception("Unsupported OS")
        return addr

    def _free(self, addr):
        if os.name == 'nt':
            MEM_RELEASE = 0x8000
            windll.kernel32.VirtualFree.argtypes = [c_void_p, c_long, c_long]
            windll.kernel32.VirtualFree.restype = c_int
            windll.kernel32.VirtualFree(c_void_p(addr), 0, MEM_RELEASE)
        elif os.name == 'posix':
            libc.free.argtypes = [c_void_p]
            libc.free(addr)
        else:
            raise Exception("Unsupported OS")


class DMABufferArray:
    def __init__(self, bytesPerSample, size, count):
        """
        bytesPerSample: 1 or 2
        size: samples per buffer
        count: number of buffers
        """
        self.count = count
        self.dtype = c_uint8 if bytesPerSample == 1 else c_uint16
        self.size = size
        self.__buffers = []
        self.__index = 0

    def __enter__(self):
        for i in range(self.count):
            buff = DMABuffer(self.dtype, self.size)
            buff.alloc()
            self.__buffers.append(buff)
        return self

    def __exit__(self, *args, **kw):
        for buff in self.__buffers:
            buff.free()

    def __iter__(self):
        return self

    def __next__(self):
        i = self.__index
        self.__index = (self.__index + 1) % self.count
        return self.__buffers[i]

    def post(self, dig):
        for buff in self.__buffers:
            dig.postAsyncBuffer(buff.addr, buff.bytes)
        dig.checkErrors()

    def reset(self):
        self.__index = 0


class AutoDMA:
    def __init__(self,
                 dig,
                 samplesPerRecord=1024,
                 repeats=0,
                 buffers=None,
                 recordsPerBuffer=1,
                 timeout=1):
        self.dig = dig
        self.samplesPerRecord = samplesPerRecord
        self.recordsPerBuffer = recordsPerBuffer
        self.repeats = repeats
        self.timeout = timeout
        self.buffers = buffers
        self.config()
        if self.buffers is not None:
            self.buffers.reset()
            if self.repeats<=0:
                self.repeats = self.buffers.count

    def config(self):
        self.dig.setRecordSize(0, self.samplesPerRecord)

    def before(self):
        flags = API.ADMA_NPT | API.ADMA_EXTERNAL_STARTCAPTURE | API.ADMA_INTERLEAVE_SAMPLES
        if self.buffers is None:
            flags |= API.ADMA_ALLOC_BUFFERS

        recordsPerAcquisition = 0x7FFFFFFF if self.repeats<=0 else 2*self.repeats

        self.dig.beforeAsyncRead(API.CHANNEL_A | API.CHANNEL_B, 0,
                                 self.samplesPerRecord, self.recordsPerBuffer,
                                 recordsPerAcquisition, flags)
        self.dig.checkErrors()

        if self.buffers is not None:
            self.buffers.post(self.dig)

    def start(self):
        self.dig.startCapture()
        self.dig.checkErrors()

    def abord(self):
        self.dig.abortAsyncRead()

    def read(self):
        codeZero = (1 << (self.dig.bitsPerSample - 1)) - 0.5
        codeRange = (1 << (self.dig.bitsPerSample - 1)) - 0.5
        scaleA = self.dig.inputRange[API.CHANNEL_A] / codeRange
        scaleB = self.dig.inputRange[API.CHANNEL_B] / codeRange

        _read = self._read if self.buffers is None else self._readIntoBuffer

        for data in _read():
            data = data - codeZero
            chA = scaleA * data[0::2]
            chB = scaleB * data[1::2]
            yield chA, chB

    def _read(self):
        channelCount = 2
        bytesPerSample = (self.dig.bitsPerSample + 7) // 8
        samplesPerBuffer = self.samplesPerRecord * self.recordsPerBuffer * channelCount
        bytesPerBuffer = bytesPerSample * samplesPerBuffer

        dtype = c_uint8 if bytesPerSample == 1 else c_uint16
        buff = (dtype * samplesPerBuffer)()

        count = 0
        while True:
            self.dig.waitNextAsyncBufferComplete(buff, bytesPerBuffer,
                                                 int(1000 * self.timeout))
            self.dig.checkErrors()
            yield np.asarray(buff)
            count += 1
            if count>=self.repeats and self.repeats>0:
                break

    def _readIntoBuffer(self):
        count = 0
        for buff in self.buffers:
            self.dig.waitAsyncBufferComplete(buff.addr,
                                             int(1000 * self.timeout))
            self.dig.checkErrors()
            yield buff.buffer
            count += 1
            if count>=self.repeats and self.repeats>0:
                break
            self.dig.postAsyncBuffer(buff.addr, buff.bytes)

    def __enter__(self):
        self.before()
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.abord()
        finally:
            pass
