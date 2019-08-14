# -*- coding: utf-8 -*-
import logging
logger = logging.getLogger('qulab.drivers.ATS')
logger.addHandler(logging.NullHandler())

logger.debug('ATS driver start loading APIs ...')

import ctypes, os
from ctypes import (c_int8, c_uint8, c_int16, c_uint16, c_int64, c_uint64,
                    c_char_p, c_wchar_p, c_void_p, c_long, c_ulong,
                    c_int, c_uint, c_float, byref, Structure, POINTER)

from .exception import AlazarTechError

c_long_p  = POINTER(c_long)
c_ulong_p = POINTER(c_ulong)
c_int_p   = POINTER(c_int)
# open dll
try:
    logger.debug('Loading ATSApi.dll ...')
    DLL = ctypes.CDLL('ATSApi')
    logger.debug('Load ATSApi.dll success.')
except:
    # if failure, try to open in driver folder
    logger.debug('Load ATSApi.dll fault.')
    path = os.path.dirname(os.path.abspath(__file__))
    logger.debug('Loading ATSApi.dll in driver folder : %s ...', path)
    DLL = ctypes.CDLL(os.path.join(path, 'ATSApi'))
    logger.debug('Load ATSApi.dll in driver folder success.')

#******************************************
# *      Windows Type Definitions
# ******************************************/
S8, PS8 = c_int8, c_char_p
U8, PU8 = c_uint8, POINTER(c_uint8)
S16, PS16 = c_int16, POINTER(c_int16)
U16, PU16 = c_uint16, POINTER(c_uint16)
S32, PS32 = c_long, POINTER(c_long)
U32, PU32 = c_ulong, POINTER(c_ulong)
S64, PS64 = c_int64, POINTER(c_int64)
U64, PU64 = c_uint64, POINTER(c_uint64)
HANDLE    = c_void_p
RETURN_CODE = c_int

# BoardTypes

ATS_NONE = 0
ATS850   = 1
ATS310   = 2
ATS330   = 3
ATS855   = 4
ATS315   = 5
ATS335   = 6
ATS460   = 7
ATS860   = 8
ATS660   = 9
ATS665   = 10
ATS9462  = 11
ATS9434  = 12
ATS9870  = 13
ATS9350  = 14
ATS9325  = 15
ATS9440  = 16
ATS9410  = 17
ATS9351  = 18
ATS9310  = 19
ATS9461  = 20
ATS9850  = 21
ATS9625  = 22
ATG6500  = 23
ATS9626  = 24
ATS9360  = 25
ATS_LAST = 26


# Board Definition structure
class BoardDef(Structure):
    _fields_ = [
    ("RecordCount", U32),
    ("RecLength", U32),
    ("PreDepth", U32),
    ("ClockSource", U32),
    ("ClockEdge", U32),
    ("SampleRate", U32),
    ("CouplingChanA", U32),
    ("InputRangeChanA", U32),
    ("InputImpedChanA", U32),
    ("CouplingChanB", U32),
    ("InputRangeChanB", U32),
    ("InputImpedChanB", U32),
    ("TriEngOperation", U32),
    ("TriggerEngine1", U32),
    ("TrigEngSource1", U32),
    ("TrigEngSlope1", U32),
    ("TrigEngLevel1", U32),
    ("TriggerEngine2", U32),
    ("TrigEngSource2", U32),
    ("TrigEngSlope2", U32),
    ("TrigEngLevel2", U32)
    ]

pBoardDef = POINTER(BoardDef)

# Constants to be used in the Application when dealing with Custom FPGAs
FPGA_GETFIRST=	0xFFFFFFFF
FPGA_GETNEXT=	0xFFFFFFFE
FPGA_GETLAST=	0xFFFFFFFC

def __get_Func(funcname, restype=None, argtypes=None):
    try:
        func = getattr(DLL, funcname)
    except:
        logger.warning('Alazar API has no function named %r' % funcname)
        def missingFunction(*args, **kw):
            raise AlazarTechError(533, 'Alazar API has no function named %r' % funcname)
        return missingFunction
    if restype != None:
        func.restype = restype
    if argtypes !=None:
        func.argtypes = argtypes
    return func

#RETURN_CODE AlazarGetOEMFPGAName(int opcodeID, char *FullPath, unsigned long *error);
AlazarGetOEMFPGAName = __get_Func("AlazarGetOEMFPGAName", RETURN_CODE, [c_int, c_char_p, c_ulong_p])
#RETURN_CODE AlazarOEMSetWorkingDirectory(char *wDir, unsigned long *error);
AlazarOEMSetWorkingDirectory = __get_Func("AlazarOEMSetWorkingDirectory", RETURN_CODE, [c_char_p, c_ulong_p])
#RETURN_CODE AlazarOEMGetWorkingDirectory(char *wDir, unsigned long *error);
AlazarOEMGetWorkingDirectory = __get_Func("AlazarOEMGetWorkingDirectory", RETURN_CODE, [c_char_p, c_ulong_p])
#RETURN_CODE AlazarParseFPGAName(const char *FullName, char *Name, U32 *Type, U32 *MemSize, U32 *MajVer, U32 *MinVer, U32 *MajRev, U32 *MinRev, U32 *error);
AlazarParseFPGAName = __get_Func("AlazarParseFPGAName", RETURN_CODE, [c_char_p, c_char_p, PU32, PU32, PU32, PU32, PU32, PU32, PU32])
#RETURN_CODE AlazarOEMDownLoadFPGA( HANDLE h,char *FileName,U32 *RetValue);
AlazarOEMDownLoadFPGA = __get_Func("AlazarOEMDownLoadFPGA", RETURN_CODE, [HANDLE, c_char_p, PU32])
#RETURN_CODE AlazarDownLoadFPGA( HANDLE h,char *FileName,U32 *RetValue);
AlazarDownLoadFPGA = __get_Func("AlazarDownLoadFPGA", RETURN_CODE, [HANDLE, c_char_p, PU32])

# ********************************************************************
# Header Constants and Structures that need to be used
# when dealing with ADMA captures that use the header.
# ********************************************************************
ADMA_CLOCKSOURCE       = 0x00000001
ADMA_CLOCKEDGE         = 0x00000002
ADMA_SAMPLERATE        = 0x00000003
ADMA_INPUTRANGE        = 0x00000004
ADMA_INPUTCOUPLING     = 0x00000005
ADMA_IMPUTIMPEDENCE    = 0x00000006
ADMA_EXTTRIGGERED      = 0x00000007
ADMA_CHA_TRIGGERED     = 0x00000008
ADMA_CHB_TRIGGERED     = 0x00000009
ADMA_TIMEOUT           = 0x0000000A
ADMA_THISCHANTRIGGERED = 0x0000000B
ADMA_SERIALNUMBER      = 0x0000000C
ADMA_SYSTEMNUMBER      = 0x0000000D
ADMA_BOARDNUMBER       = 0x0000000E
ADMA_WHICHCHANNEL      = 0x0000000F
ADMA_SAMPLERESOLUTION  = 0x00000010
ADMA_DATAFORMAT        = 0x00000011

class _HEADER0(Structure):
    _fields_ = [
    ("SerialNumber", c_uint, 18),
    ("SystemNumber", c_uint, 4),
    ("WhichChannel", c_uint, 1),
    ("BoardNumber",  c_uint, 4),
    ("SampleResolution", c_uint, 3),
    ("DataFormat",   c_uint, 2)
    ]

class _HEADER1(Structure):
    _fields_ = [
    ("RecordNumber", c_uint, 24),
    ("BoardType", c_uint, 8)
    ]

class _HEADER2(Structure):
    _fields_ = [
    ("TimeStampLowPart", U32)
    ]

class _HEADER3(Structure):
    _fields_ = [
    ("TimeStampHighPart", c_uint, 8),
    ("ClockSource",       c_uint, 2),
    ("ClockEdge",         c_uint, 1),
    ("SampleRate",        c_uint, 7),
    ("InputRange",        c_uint, 5),
    ("InputCoupling",     c_uint, 2),
    ("InputImpedence",    c_uint, 2),
    ("ExternalTriggered", c_uint, 1),
    ("ChannelBTriggered", c_uint, 1),
    ("ChannelATriggered", c_uint, 1),
    ("TimeOutOccurred",   c_uint, 1),
    ("ThisChannelTriggered", c_uint, 1)
    ]

class ALAZAR_HEADER(Structure):
    _fields_ = [
    ("hdr0", _HEADER0),
    ("hdr1", _HEADER1),
    ("hdr2", _HEADER2),
    ("hdr3", _HEADER3)
    ]
PALAZAR_HEADER = POINTER(ALAZAR_HEADER)


# AUTODMA_STATUS:
AUTODMA_STATUS = c_int
P_AUTODMA_STATUS = c_int_p

ADMA_Completed = 0
ADMA_Buffer1Invalid = 1
ADMA_Buffer2Invalid = 2
ADMA_BoardHandleInvalid = 3
ADMA_InternalBuffer1Invalid = 4
ADMA_InternalBuffer2Invalid = 5
ADMA_OverFlow = 6
ADMA_InvalidChannel = 7
ADMA_DMAInProgress = 8
ADMA_UseHeaderNotSet = 9
ADMA_HeaderNotValid = 10
ADMA_InvalidRecsPerBuffer = 11
ADMA_InvalidTransferOffset = 12
ADMA_InvalidCFlags = 13

ADMA_Success = ADMA_Completed

# ****************************************************************************************
# ALAZAR CUSTOMER SUPPORT API
#
# Global API Functions
# MSILS:
MSILS = c_int
KINDEPENDENT = 0
KSLAVE = 1
KMASTER = 2
KLASTSLAVE = 3
#******************************************
# Trouble Shooting Alazar Functions
#*****************************************/

#RETURN_CODE AlazarReadWriteTest( HANDLE h,U32 *Buffer,U32 SizeToWrite,U32 SizeToRead);
AlazarReadWriteTest = __get_Func("AlazarReadWriteTest", RETURN_CODE, [HANDLE, PU32, U32, U32])
#RETURN_CODE AlazarMemoryTest( HANDLE h, U32 *errors );
AlazarMemoryTest = __get_Func("AlazarMemoryTest", RETURN_CODE, [HANDLE, PU32])
#RETURN_CODE AlazarBusyFlag( HANDLE h,int *BusyFlag);
AlazarBusyFlag = __get_Func("AlazarBusyFlag", RETURN_CODE, [HANDLE, c_int_p])
#RETURN_CODE AlazarTriggeredFlag( HANDLE h,int *TriggeredFlag);
AlazarTriggeredFlag = __get_Func("AlazarTriggeredFlag", RETURN_CODE, [HANDLE, c_int_p])
#U32	      AlazarBoardsFound();
AlazarBoardsFound = __get_Func("AlazarBoardsFound", U32, None)
#HANDLE      AlazarOpen( char * BoardNameID); //e.x. ATS850-0, ATS850-1 ....
AlazarOpen = __get_Func("AlazarOpen", HANDLE, [c_char_p])
#void        AlazarClose( HANDLE h);
AlazarClose = __get_Func("AlazarClose", None, [HANDLE])
#MSILS       AlazarGetBoardKind( HANDLE h);
AlazarGetBoardKind = __get_Func("AlazarGetBoardKind", MSILS, [HANDLE])
#RETURN_CODE AlazarGetCPLDVersion( HANDLE h,U8 *Major,U8 *Minor);
AlazarGetCPLDVersion = __get_Func("AlazarGetCPLDVersion", RETURN_CODE, [HANDLE, PU8, PU8])
#RETURN_CODE AlazarGetChannelInfo( HANDLE h, U32 *MemSize, U8 *SampleSize);
AlazarGetChannelInfo = __get_Func("AlazarGetChannelInfo", RETURN_CODE, [HANDLE, PU32, PU8])
#RETURN_CODE AlazarGetSDKVersion(U8 *Major,U8 *Minor,U8 *Revision);
AlazarGetSDKVersion = __get_Func("AlazarGetSDKVersion", RETURN_CODE, [PU8, PU8, PU8])
#RETURN_CODE AlazarGetDriverVersion(U8 *Major,U8 *Minor,U8 *Revision);
AlazarGetDriverVersion = __get_Func("AlazarGetDriverVersion", RETURN_CODE, [PU8, PU8, PU8])
# ****************************************************************************************
# Input Control API Functions
#RETURN_CODE  AlazarInputControl( HANDLE h, U8 Channel, U32 Coupling, U32 InputRange, U32 Impedance);
AlazarInputControl = __get_Func("AlazarInputControl", RETURN_CODE, [HANDLE, U8, U32, U32, U32])
#RETURN_CODE  AlazarSetPosition( HANDLE h, U8 Channel, int PMPercent, U32 InputRange);
AlazarSetPosition = __get_Func("AlazarSetPosition", RETURN_CODE, [HANDLE, U8, c_int, U32])
#RETURN_CODE  AlazarSetExternalTrigger( HANDLE h, U32 Coupling, U32 Range);
AlazarSetExternalTrigger = __get_Func("AlazarSetExternalTrigger", RETURN_CODE, [HANDLE, U32, U32])
# ****************************************************************************************
# Trigger API Functions
#RETURN_CODE  AlazarSetTriggerDelay( HANDLE h, U32 Delay);
AlazarSetTriggerDelay = __get_Func("AlazarSetTriggerDelay", RETURN_CODE, [HANDLE, U32])
#RETURN_CODE  AlazarSetTriggerTimeOut( HANDLE h, U32 to_ns);
AlazarSetTriggerTimeOut = __get_Func("AlazarSetTriggerTimeOut", RETURN_CODE, [HANDLE, U32])
#U32          AlazarTriggerTimedOut( HANDLE h);
AlazarTriggerTimedOut = __get_Func("AlazarTriggerTimedOut", U32, [HANDLE])
#RETURN_CODE  AlazarGetTriggerAddress( HANDLE h, U32 Record, U32 *TriggerAddress, U32 *TimeStampHighPart, U32 *TimeStampLowPart);
AlazarGetTriggerAddress = __get_Func("AlazarGetTriggerAddress", RETURN_CODE, [HANDLE, U32, PU32, PU32, PU32])
#RETURN_CODE  AlazarSetTriggerOperation( HANDLE h, U32 TriggerOperation
#											  ,U32 TriggerEngine1/*j,K*/, U32 Source1, U32 Slope1, U32 Level1
#											  ,U32 TriggerEngine2/*j,K*/, U32 Source2, U32 Slope2, U32 Level2);
AlazarSetTriggerOperation = __get_Func("AlazarSetTriggerOperation", RETURN_CODE, [HANDLE, U32, U32, U32, U32, U32, U32, U32, U32, U32])
#RETURN_CODE	 AlazarGetTriggerTimestamp(HANDLE h, U32 Record, U64* Timestamp_samples);
AlazarGetTriggerTimestamp = __get_Func("AlazarGetTriggerTimestamp", RETURN_CODE, [HANDLE, U32, PU64])
#RETURN_CODE  AlazarSetTriggerOperationForScanning(HANDLE h, U32 slope, U32 level, U32 options);
AlazarSetTriggerOperationForScanning = __get_Func("AlazarSetTriggerOperationForScanning", RETURN_CODE, [HANDLE, U32, U32, U32])

# ****************************************************************************************
# Capture API Functions
#RETURN_CODE  AlazarAbortCapture( HANDLE h);
AlazarAbortCapture = __get_Func("AlazarAbortCapture", RETURN_CODE, [HANDLE])
#RETURN_CODE  AlazarForceTrigger( HANDLE h);
AlazarForceTrigger = __get_Func("AlazarForceTrigger", RETURN_CODE, [HANDLE])
#RETURN_CODE	 AlazarForceTriggerEnable( HANDLE h);
AlazarForceTriggerEnable = __get_Func("AlazarForceTriggerEnable", RETURN_CODE, [HANDLE])
#RETURN_CODE  AlazarStartCapture( HANDLE h);
AlazarStartCapture = __get_Func("AlazarStartCapture", RETURN_CODE, [HANDLE])
#RETURN_CODE  AlazarCaptureMode( HANDLE h, U32 Mode);
AlazarCaptureMode = __get_Func("AlazarCaptureMode", RETURN_CODE, [HANDLE, U32])

# ****************************************************************************************
# OEM API Functions
#RETURN_CODE AlazarStreamCapture(
#								HANDLE		h,
#								void 		*Buffer,
#								U32			BufferSize,
#								U32			DeviceOption,
#								U32			ChannelSelect,
#								U32			*error
#								);
AlazarStreamCapture = __get_Func("AlazarStreamCapture", RETURN_CODE, [HANDLE, c_void_p, U32, U32, U32, PU32])

#RETURN_CODE AlazarHyperDisp(
#							HANDLE		h,
#							void 		*Buffer,
#							U32			BufferSize,
#							U8			*ViewBuffer,
#							U32			ViewBufferSize,
#							U32			NumOfPixels,
#							U32			Option,
#							U32			ChannelSelect,
#							U32			Record,
#							long		TransferOffset,
#							U32			*error
#							);
AlazarHyperDisp = __get_Func("AlazarHyperDisp", RETURN_CODE, [HANDLE, c_void_p, U32, PU8, U32, U32, U32, U32, U32, c_long, PU32])

#RETURN_CODE AlazarFastPRRCapture(
#							HANDLE		h,
#							void 		*Buffer,
#							U32			BufferSize,
#							U32			DeviceOption,
#							U32			ChannelSelect,
#							U32			*error
#							);
AlazarFastPRRCapture = __get_Func("AlazarFastPRRCapture", RETURN_CODE, [HANDLE, c_void_p, U32, U32, U32, PU32])

# ****************************************************************************************
# Status API Functions
#U32	AlazarBusy( HANDLE h);
AlazarBusy = __get_Func("AlazarBusy", U32, [HANDLE])
#U32	AlazarTriggered( HANDLE h);
AlazarTriggered = __get_Func("AlazarTriggered", U32, [HANDLE])
#U32	AlazarGetStatus( HANDLE h);
AlazarGetStatus = __get_Func("AlazarGetStatus", U32, [HANDLE])
# ****************************************************************************************
# MulRec API Functions
#U32         AlazarDetectMultipleRecord( HANDLE h);
AlazarDetectMultipleRecord = __get_Func("AlazarDetectMultipleRecord", U32, [HANDLE])
#RETURN_CODE AlazarSetRecordCount( HANDLE h, U32 Count);
AlazarSetRecordCount = __get_Func("AlazarSetRecordCount", RETURN_CODE, [HANDLE, U32])
#RETURN_CODE AlazarSetRecordSize( HANDLE h, U32 PreSize, U32 PostSize);
AlazarSetRecordSize = __get_Func("AlazarSetRecordSize", RETURN_CODE, [HANDLE, U32, U32])

# ****************************************************************************************
# Clock Control API Functions
#RETURN_CODE AlazarSetCaptureClock( HANDLE h, U32 Source, U32 Rate, U32 Edge, U32 Decimation);
AlazarSetCaptureClock = __get_Func("AlazarSetCaptureClock", RETURN_CODE, [HANDLE, U32, U32, U32, U32])
#RETURN_CODE AlazarSetExternalClockLevel( HANDLE h, float percent);
AlazarSetExternalClockLevel = __get_Func("AlazarSetExternalClockLevel", RETURN_CODE, [HANDLE, c_float])
#RETURN_CODE AlazarSetClockSwitchOver(HANDLE hBoard, U32 uMode, U32 uDummyClockOnTime_ns, U32 uReserved);
AlazarSetClockSwitchOver = __get_Func("AlazarSetClockSwitchOver", RETURN_CODE, [HANDLE, U32, U32, U32])

CSO_DISABLE                 = 0
CSO_ENABLE_DUMMY_CLOCK      = 1
CSO_TRIGGER_LOW_DUMMY_CLOCK = 2

# ****************************************************************************************
# Data Transfer API Functions
#U32	AlazarRead( HANDLE h, U32 Channel, void *Buffer, int ElementSize, long Record, long TransferOffset, U32 TransferLength);
AlazarRead = __get_Func("AlazarRead", U32, [HANDLE, U32, c_void_p, c_int, c_long, c_long, U32])

# ****************************************************************************************
# Individual Parameter API Functions
#RETURN_CODE AlazarSetParameter( HANDLE h,U8 Channel,U32 Parameter,long Value);
AlazarSetParameter = __get_Func("AlazarSetParameter", RETURN_CODE, [HANDLE, U8, U32, c_long])
#RETURN_CODE AlazarSetParameterUL( HANDLE h,U8 Channel,U32 Parameter,U32 Value);
AlazarSetParameterUL = __get_Func("AlazarSetParameterUL", RETURN_CODE, [HANDLE, U8, U32, U32])
#RETURN_CODE AlazarGetParameter( HANDLE h,U8 Channel,U32 Parameter,long *RetValue);
AlazarGetParameter = __get_Func("AlazarGetParameter", RETURN_CODE, [HANDLE, U8, U32, c_long_p])
#RETURN_CODE AlazarGetParameterUL( HANDLE h,U8 Channel,U32 Parameter,U32 *RetValue);
AlazarGetParameterUL = __get_Func("AlazarGetParameterUL", RETURN_CODE, [HANDLE, U8, U32, PU32])

# ****************************************************************************************
# Handle and System Management API Functions
#HANDLE AlazarGetSystemHandle(U32 sid);
AlazarGetSystemHandle = __get_Func("AlazarGetSystemHandle", HANDLE, [U32])
#U32 AlazarNumOfSystems();
AlazarNumOfSystems = __get_Func("AlazarNumOfSystems", U32, None)
#U32 AlazarBoardsInSystemBySystemID(U32 sid);
AlazarBoardsInSystemBySystemID = __get_Func("AlazarBoardsInSystemBySystemID", U32, [U32])
#U32 AlazarBoardsInSystemByHandle(HANDLE systemHandle);
AlazarBoardsInSystemByHandle = __get_Func("AlazarBoardsInSystemByHandle", U32, [HANDLE])
#HANDLE AlazarGetBoardBySystemID(U32 sid, U32 brdNum);
AlazarGetBoardBySystemID = __get_Func("AlazarGetBoardBySystemID", HANDLE, [U32, U32])
#HANDLE AlazarGetBoardBySystemHandle(HANDLE systemHandle, U32 brdNum);
AlazarGetBoardBySystemHandle = __get_Func("AlazarGetBoardBySystemHandle", HANDLE, [HANDLE, U32])
#RETURN_CODE AlazarSetLED( HANDLE h, U32 state);
AlazarSetLED = __get_Func("AlazarSetLED", c_int, [HANDLE, U32])

# ****************************************************************************************
# Board capability query functions
#RETURN_CODE AlazarQueryCapability(HANDLE h, U32 request, U32 value, U32 *retValue);
AlazarQueryCapability = __get_Func("AlazarQueryCapability", RETURN_CODE, [HANDLE, U32, U32, PU32])
#U32 AlazarMaxSglTransfer(ALAZAR_BOARDTYPES bt);
AlazarMaxSglTransfer = __get_Func("AlazarMaxSglTransfer", U32, [c_int])
#RETURN_CODE AlazarGetMaxRecordsCapable(HANDLE h, U32 RecordLength, U32 *num);
AlazarGetMaxRecordsCapable = __get_Func("AlazarGetMaxRecordsCapable", RETURN_CODE, [HANDLE, U32, PU32])

# ****************************************************************************************
# Trigger Inquiry Functions
# Return values:
#              NEITHER   = 0
#              Channel A = 1
#              Channel B = 2
#              External  = 3
#              A AND B   = 4
#              A AND Ext = 5
#              B And Ext = 6
#              Timeout   = 7
#U32 AlazarGetWhoTriggeredBySystemHandle( HANDLE systemHandle, U32 brdNum, U32 recNum);
AlazarGetWhoTriggeredBySystemHandle = __get_Func("AlazarGetWhoTriggeredBySystemHandle", U32, [HANDLE, U32, U32])
#U32 AlazarGetWhoTriggeredBySystemID( U32 sid, U32 brdNum, U32 recNum);
AlazarGetWhoTriggeredBySystemID = __get_Func("AlazarGetWhoTriggeredBySystemID", U32, [U32, U32, U32])

#RETURN_CODE AlazarSetBWLimit( HANDLE h, U32 Channel, U32 enable);
AlazarSetBWLimit = __get_Func("AlazarSetBWLimit", RETURN_CODE, [HANDLE, U32, U32])
#RETURN_CODE AlazarSleepDevice( HANDLE h, U32 state);
AlazarSleepDevice = __get_Func("AlazarSleepDevice", RETURN_CODE, [HANDLE, U32])

# AUTODMA Related Routines
#
# Control Flags for AutoDMA used in AlazarStartAutoDMA
ADMA_EXTERNAL_STARTCAPTURE = 0x00000001
ADMA_ENABLE_RECORD_HEADERS = 0x00000008
ADMA_SINGLE_DMA_CHANNEL    = 0x00000010
ADMA_ALLOC_BUFFERS         = 0x00000020
ADMA_TRADITIONAL_MODE      = 0x00000000
ADMA_CONTINUOUS_MODE       = 0x00000100
ADMA_NPT                   = 0x00000200
ADMA_TRIGGERED_STREAMING   = 0x00000400
ADMA_FIFO_ONLY_STREAMING   = 0x00000800 # ATS9462 mode
ADMA_INTERLEAVE_SAMPLES    = 0x00001000
ADMA_GET_PROCESSED_DATA    = 0x00002000

#RETURN_CODE  AlazarStartAutoDMA(HANDLE h, void* Buffer1, U32 UseHeader, U32 ChannelSelect, long TransferOffset, U32 TransferLength, long RecordsPerBuffer, long RecordCount, AUTODMA_STATUS* error, U32 r1, U32 r2, U32 *r3, U32 *r4);
AlazarStartAutoDMA = __get_Func("AlazarStartAutoDMA", RETURN_CODE, [HANDLE, c_void_p, U32, U32, c_long, U32, c_long, c_long, P_AUTODMA_STATUS, U32, U32, PU32, PU32])
#RETURN_CODE  AlazarGetNextAutoDMABuffer( HANDLE h, void* Buffer1, void* Buffer2, long* WhichOne, long* RecordsTransfered, AUTODMA_STATUS* error, U32 r1, U32 r2, long *TriggersOccurred, U32 *r4);
AlazarGetNextAutoDMABuffer = __get_Func("AlazarGetNextAutoDMABuffer", RETURN_CODE, [HANDLE, c_void_p, c_void_p, c_long_p, c_long_p, P_AUTODMA_STATUS, U32, U32, c_long_p, PU32])
#RETURN_CODE  AlazarGetNextBuffer( HANDLE h, void* Buffer1, void* Buffer2, long* WhichOne, long* RecordsTransfered, AUTODMA_STATUS* error, U32 r1, U32 r2, long *TriggersOccurred, U32 *r4);
AlazarGetNextBuffer = __get_Func("AlazarGetNextBuffer", RETURN_CODE, [HANDLE, c_void_p, c_void_p, c_long_p, c_long_p, P_AUTODMA_STATUS, U32, U32, c_long_p, PU32])
#RETURN_CODE  AlazarCloseAUTODma(HANDLE h);
AlazarCloseAUTODma = __get_Func("AlazarCloseAUTODma", RETURN_CODE, [HANDLE])
#RETURN_CODE  AlazarAbortAutoDMA(HANDLE h, void* Buffer, AUTODMA_STATUS* error, U32 r1, U32 r2, U32 *r3, U32 *r4);
AlazarAbortAutoDMA = __get_Func("AlazarAbortAutoDMA", RETURN_CODE, [HANDLE, c_void_p, P_AUTODMA_STATUS, U32, U32, PU32, PU32])
#U32  AlazarGetAutoDMAHeaderValue(HANDLE h, U32 Channel, void* DataBuffer, U32 Record, U32 Parameter, AUTODMA_STATUS *error);
AlazarGetAutoDMAHeaderValue = __get_Func("AlazarGetAutoDMAHeaderValue", U32, [HANDLE, U32, c_void_p, U32, U32, P_AUTODMA_STATUS])
#float  AlazarGetAutoDMAHeaderTimeStamp(HANDLE h, U32 Channel, void* DataBuffer, U32 Record, AUTODMA_STATUS *error);
AlazarGetAutoDMAHeaderTimeStamp = __get_Func("AlazarGetAutoDMAHeaderTimeStamp", c_float, [HANDLE, U32, c_void_p, U32, P_AUTODMA_STATUS])
#void  *AlazarGetAutoDMAPtr(HANDLE h, U32 DataOrHeader, U32 Channel, void* DataBuffer, U32 Record, AUTODMA_STATUS *error);
AlazarGetAutoDMAPtr = __get_Func("AlazarGetAutoDMAPtr", c_void_p, [HANDLE, U32, U32, c_void_p, U32, P_AUTODMA_STATUS])
#U32  AlazarWaitForBufferReady(HANDLE h, long tms);
AlazarWaitForBufferReady = __get_Func("AlazarWaitForBufferReady", U32, [HANDLE, c_long])
#RETURN_CODE  AlazarEvents(HANDLE h, U32 enable);
AlazarEvents = __get_Func("AlazarEvents", RETURN_CODE, [HANDLE, U32])
#RETURN_CODE
#AlazarBeforeAsyncRead (
#	HANDLE	hBoard,
#	U32		uChannelSelect,
#	long	lTransferOffset,
#	U32		uSamplesPerRecord,
#	U32		uRecordsPerBuffer,
#	U32		uRecordsPerAcquisition,
#	U32		uFlags
#	);
AlazarBeforeAsyncRead = __get_Func("AlazarBeforeAsyncRead", RETURN_CODE, [HANDLE, U32, c_long, U32, U32, U32, U32])
#include "windows.h"
#typedef struct _OVERLAPPED {
#　　DWORD Internal;
#　　DWORD InternalHigh;
#　　DWORD Offset;
#　　DWORD OffsetHigh;
#　　HANDLE hEvent;
#　　} OVERLAPPED
class OVERLAPPED(Structure):
    _fields_ = [
    ("Internal", c_ulong),
    ("InternalHigh", c_ulong),
    ("Offset", c_ulong),
    ("OffsetHigh", c_ulong),
    ("hEvent", HANDLE)
    ]
P_OVERLAPPED = POINTER(OVERLAPPED)

#RETURN_CODE
#AlazarAsyncRead (
#	HANDLE	    hBoard,
#	void       *pBuffer,
#	U32		    BytesToRead,
#	OVERLAPPED *pOverlapped
#	);
AlazarAsyncRead = __get_Func("AlazarAsyncRead", RETURN_CODE, [HANDLE, c_void_p, U32, P_OVERLAPPED])

#RETURN_CODE
#AlazarAbortAsyncRead (
#	HANDLE	 hBoard
#	);
AlazarAbortAsyncRead = __get_Func("AlazarAbortAsyncRead", RETURN_CODE, [HANDLE])

#RETURN_CODE
#AlazarPostAsyncBuffer (
#	HANDLE  hDevice,
#	void   *pBuffer,
#	U32     uBufferLength_bytes
#	);
AlazarPostAsyncBuffer = __get_Func("AlazarPostAsyncBuffer", RETURN_CODE, [HANDLE, c_void_p, U32])

#RETURN_CODE
#AlazarWaitAsyncBufferComplete (
#	HANDLE  hDevice,
#	void   *pBuffer,
#	U32     uTimeout_ms
#	);
AlazarWaitAsyncBufferComplete = __get_Func("AlazarWaitAsyncBufferComplete", RETURN_CODE, [HANDLE, c_void_p, U32])

#RETURN_CODE
#AlazarWaitNextAsyncBufferComplete (
#	HANDLE  hDevice,
#	void   *pBuffer,
#	U32     uBufferLength_bytes,
#	U32     uTimeout_ms
#	);
AlazarWaitNextAsyncBufferComplete = __get_Func("AlazarWaitNextAsyncBufferComplete", RETURN_CODE, [HANDLE, c_void_p, U32, U32])

#RETURN_CODE
#AlazarCreateStreamFileA (
#	HANDLE hDevice,
#	const char *pszFilePath
#	);
AlazarCreateStreamFileA = __get_Func("AlazarCreateStreamFileA", RETURN_CODE, [HANDLE, c_char_p])

#RETURN_CODE
#AlazarCreateStreamFileW (
#	HANDLE hDevice,
#	const WCHAR *pszFilePath
#	);
AlazarCreateStreamFileW = __get_Func("AlazarCreateStreamFileW", RETURN_CODE, [HANDLE, c_wchar_p])

#ifdef UNICODE
#define AlazarCreateStreamFile AlazarCreateStreamFileW
#else
#define AlazarCreateStreamFile AlazarCreateStreamFileA
#endif
AlazarCreateStreamFile = AlazarCreateStreamFileW

#long AlazarFlushAutoDMA(HANDLE h);
AlazarFlushAutoDMA = __get_Func("AlazarFlushAutoDMA", c_long, [HANDLE])
#void AlazarStopAutoDMA(HANDLE h);
AlazarStopAutoDMA = __get_Func("AlazarStopAutoDMA", None, [HANDLE])

# TimeStamp Control Api
#RETURN_CODE AlazarResetTimeStamp(HANDLE h, U32 resetFlag);
AlazarResetTimeStamp = __get_Func("AlazarResetTimeStamp", RETURN_CODE, [HANDLE, U32])

#RETURN_CODE AlazarReadRegister(HANDLE hDevice,U32 offset,U32 *retVal, U32 pswrd);
AlazarReadRegister = __get_Func("AlazarReadRegister", RETURN_CODE, [HANDLE, U32, PU32, U32])
#RETURN_CODE AlazarWriteRegister(HANDLE hDevice,U32 offset,U32 Val, U32 pswrd);
AlazarWriteRegister = __get_Func("AlazarWriteRegister", RETURN_CODE, [HANDLE, U32, U32, U32])

#
# DAC CONTROL API
#RETURN_CODE AlazarDACSetting
#(HANDLE h, U32 SetGet, U32 OriginalOrModified, U8 Channel, U32 DACNAME, U32 Coupling, U32 InputRange, U32 Impedance, U32 *getVal, U32 setVal, U32 *error);
AlazarDACSetting = __get_Func("AlazarDACSetting", RETURN_CODE, [HANDLE, U32, U32, U8, U32, U32, U32, U32, PU32, U32, PU32])

#RETURN_CODE
#AlazarConfigureAuxIO (
#	HANDLE		hDevice,
#	U32			uMode,
#	U32			uParameter
#	);
AlazarConfigureAuxIO = __get_Func("AlazarConfigureAuxIO", RETURN_CODE, [HANDLE, U32, U32])

# Convert RETURN_CODE to text
#const char *
#AlazarErrorToText(
#	RETURN_CODE code
#	);
AlazarErrorToText = __get_Func("AlazarErrorToText", c_char_p, [RETURN_CODE])

# sample skipping

#RETURN_CODE
#AlazarConfigureSampleSkipping (
#	HANDLE  hBoard,
#	U32		uMode,
#	U32     uSampleClocksPerRecord,
#	U16    *pwClockSkipMask
#	);
AlazarConfigureSampleSkipping = __get_Func("AlazarConfigureSampleSkipping", RETURN_CODE, [HANDLE, U32, U32, U16])

# coporocessor API

#RETURN_CODE	AlazarCoprocessorRegisterRead (HANDLE hDevice, U32 offset, U32 *pValue);
AlazarCoprocessorRegisterRead = __get_Func("AlazarCoprocessorRegisterRead", RETURN_CODE, [HANDLE, U32, PU32])
#RETURN_CODE AlazarCoprocessorRegisterWrite (HANDLE hDevice, U32 offset, U32 value);
AlazarCoprocessorRegisterWrite = __get_Func("AlazarCoprocessorRegisterWrite", RETURN_CODE, [HANDLE, U32, U32])
#RETURN_CODE AlazarCoprocessorDownloadA (HANDLE hBoard, char *pszFileName, U32 uOptions);
AlazarCoprocessorDownloadA = __get_Func("AlazarCoprocessorDownloadA", RETURN_CODE, [HANDLE, c_char_p, U32])
#RETURN_CODE AlazarCoprocessorDownloadW (HANDLE hBoard, WCHAR *pszFileName, U32 uOptions);
AlazarCoprocessorDownloadW = __get_Func("AlazarCoprocessorDownloadW", RETURN_CODE, [HANDLE, c_wchar_p, U32])
#ifdef UNICODE
#define AlazarCoprocessorDownload AlazarCoprocessorDownloadW
#else
#define AlazarCoprocessorDownload AlazarCoprocessorDownloadA
#endif
AlazarCoprocessorDownload = AlazarCoprocessorDownloadW
# board revision

#RETURN_CODE
#AlazarGetBoardRevision(
#	HANDLE hBoard,
#	U8 *Major,
#	U8 *Minor
#	);
AlazarGetBoardRevision = __get_Func("AlazarGetBoardRevision", RETURN_CODE, [HANDLE, PU8, PU8])

# FPGA averaging

#RETURN_CODE
#AlazarConfigureRecordAverage(
#	HANDLE hBoard,
#	U32 uMode,
#	U32 uSamplesPerRecord,
#	U32 uRecordsPerAverage,
#	U32 uOptions
#	);
AlazarConfigureRecordAverage = __get_Func("AlazarConfigureRecordAverage", RETURN_CODE, [HANDLE, U32, U32, U32, U32])

CRA_MODE_DISABLE         = 0
CRA_MODE_ENABLE_FPGA_AVE = 1

CRA_OPTION_UNSIGNED      = (0 << 1)
CRA_OPTION_SIGNED        = (1 << 1)

# Memory allocation

#U8*
#AlazarAllocBufferU8 (
#	HANDLE hBoard,
#	U32 uSampleCount
#	);
AlazarAllocBufferU8 = __get_Func("AlazarAllocBufferU8", PU8, [HANDLE, U32])

#RETURN_CODE
#AlazarFreeBufferU8 (
#	HANDLE hBoard,
#	U8 *pBuffer
#	);
AlazarFreeBufferU8 = __get_Func("AlazarFreeBufferU8", RETURN_CODE, [HANDLE, PU8])

#U16*
#AlazarAllocBufferU16 (
#	HANDLE hBoard,
#	U32 uSampleCount
#	);
AlazarAllocBufferU16 = __get_Func("AlazarAllocBufferU16", PU16, [HANDLE, U32])

#RETURN_CODE
#AlazarFreeBufferU16 (
#	HANDLE hBoard,
#	U16 *pBuffer
#	);
AlazarFreeBufferU16 = __get_Func("AlazarFreeBufferU16", RETURN_CODE, [HANDLE, PU16])


# AlazarError.h

# RETURN_CODE:
ApiSuccess = 512
ApiFailed 								= 513
ApiAccessDenied 						= 514
ApiDmaChannelUnavailable 				= 515
ApiDmaChannelInvalid 					= 516
ApiDmaChannelTypeError 					= 517
ApiDmaInProgress 						= 518
ApiDmaDone 								= 519
ApiDmaPaused 							= 520
ApiDmaNotPaused 						= 521
ApiDmaCommandInvalid 					= 522
ApiDmaManReady 							= 523
ApiDmaManNotReady 						= 524
ApiDmaInvalidChannelPriority 			= 525
ApiDmaManCorrupted 						= 526
ApiDmaInvalidElementIndex 				= 527
ApiDmaNoMoreElements 					= 528
ApiDmaSglInvalid 						= 529
ApiDmaSglQueueFull 						= 530
ApiNullParam 							= 531
ApiInvalidBusIndex 						= 532
ApiUnsupportedFunction 					= 533
ApiInvalidPciSpace 						= 534
ApiInvalidIopSpace 						= 535
ApiInvalidSize 							= 536
ApiInvalidAddress 						= 537
ApiInvalidAccessType 					= 538
ApiInvalidIndex 						= 539
ApiMuNotReady 							= 540
ApiMuFifoEmpty 							= 541
ApiMuFifoFull 							= 542
ApiInvalidRegister 						= 543
ApiDoorbellClearFailed 					= 544
ApiInvalidUserPin 						= 545
ApiInvalidUserState 					= 546
ApiEepromNotPresent 					= 547
ApiEepromTypeNotSupported 				= 548
ApiEepromBlank 							= 549
ApiConfigAccessFailed 					= 550
ApiInvalidDeviceInfo 					= 551
ApiNoActiveDriver 						= 552
ApiInsufficientResources 				= 553
ApiObjectAlreadyAllocated 				= 554
ApiAlreadyInitialized 					= 555
ApiNotInitialized 						= 556
ApiBadConfigRegEndianMode 				= 557
ApiInvalidPowerState 					= 558
ApiPowerDown 							= 559
ApiFlybyNotSupported 					= 560
ApiNotSupportThisChannel 				= 561
ApiNoAction 							= 562
ApiHSNotSupported 						= 563
ApiVPDNotSupported 						= 564
ApiVpdNotEnabled 						= 565
ApiNoMoreCap 							= 566
ApiInvalidOffset 						= 567
ApiBadPinDirection 						= 568
ApiPciTimeout 							= 569
ApiDmaChannelClosed 					= 570
ApiDmaChannelError 						= 571
ApiInvalidHandle 						= 572
ApiBufferNotReady 						= 573
ApiInvalidData 							= 574
ApiDoNothing 							= 575
ApiDmaSglBuildFailed 					= 576
ApiPMNotSupported 						= 577
ApiInvalidDriverVersion 				= 578
ApiWaitTimeout 							= 579
ApiWaitCanceled 						= 580
ApiBufferTooSmall 						= 581
ApiBufferOverflow 						= 582
ApiInvalidBuffer 						= 583
ApiInvalidRecordsPerBuffer 				= 584
ApiDmaPending 							= 585
ApiLockAndProbePagesFailed 				= 586
ApiWaitAbandoned 						= 587
ApiWaitFailed 							= 588
ApiTransferComplete 					= 589
ApiPllNotLocked 						= 590
ApiNotSupportedInDualChannelMode        = 591
ApiNotSupportedInQuadChannelMode 		= 592
ApiFileIoError 							= 593
ApiInvalidClockFrequency 				= 594
ApiLastError						= 595 # Do not add API errors below this line


# AlazarCmd.h

# MemorySizesPerChannel
MEM8K=0
MEM64K=1
MEM128K=2
MEM256K=3
MEM512K=4
MEM1M=5
MEM2M=6
MEM4M=7
MEM8M=8
MEM16M=9
MEM32M=10
MEM64M=11
MEM128M=12
MEM256M=13
MEM512M=14
MEM1G=15
MEM2G=16
MEM4G=17
MEM8G=18
MEM16G=19

# *****************************************************************************
#
#	Configuration/Acquisition/Generation Command Set
#
# *****************************************************************************
# sets and gets
NUMBER_OF_RECORDS	=			0x10000001
PRETRIGGER_AMOUNT	=			0x10000002
RECORD_LENGTH			=		0x10000003 # rec.length-pre
TRIGGER_ENGINE		=			0x10000004
TRIGGER_DELAY			=		0x10000005
TRIGGER_TIMEOUT		=			0x10000006
SAMPLE_RATE			=			0x10000007
CONFIGURATION_MODE	=			0x10000008 # Independent  Master/Slave, Last Slave
DATA_WIDTH				=		0x10000009 # 8,16,32 bits - Digital IO boards
SAMPLE_SIZE			=			DATA_WIDTH   # 8,12,16 - Analog Input boards
AUTO_CALIBRATE		=			0x1000000A
TRIGGER_XXXXX			=		0x1000000B
CLOCK_SOURCE			=		0x1000000C
CLOCK_SLOPE			=			0x1000000D
IMPEDANCE				=		0x1000000E
INPUT_RANGE			=			0x1000000F
COUPLING				=		0x10000010
MAX_TIMEOUTS_ALLOWED=			0x10000011
OPERATING_MODE			=		0x10000012 # Single, Dual, Quad etc...
CLOCK_DECIMATION_EXTERNAL=		0x10000013
LED_CONTROL					=	0x10000014
ATTENUATOR_RELAY			=	0x10000018
EXT_TRIGGER_COUPLING		=	0x1000001A
EXT_TRIGGER_ATTENUATOR_RELAY=	0x1000001C
TRIGGER_ENGINE_SOURCE		=	0x1000001E
TRIGGER_ENGINE_SLOPE		=	0x10000020
SEND_DAC_VALUE				=	0x10000021
SLEEP_DEVICE				=	0x10000022
GET_DAC_VALUE				=	0x10000023
GET_SERIAL_NUMBER		=		0x10000024
GET_FIRST_CAL_DATE		=		0x10000025
GET_LATEST_CAL_DATE	=			0x10000026
GET_LATEST_TEST_DATE	=		0x10000027
SEND_RELAY_VALUE		=		0x10000028
GET_LATEST_CAL_DATE_MONTH	=	0x1000002D
GET_LATEST_CAL_DATE_DAY		=	0x1000002E
GET_LATEST_CAL_DATE_YEAR	=	0x1000002F
GET_PCIE_LINK_SPEED			=	0x10000030
GET_PCIE_LINK_WIDTH			=	0x10000031
SETGET_ASYNC_BUFFSIZE_BYTES=		0x10000039
SETGET_ASYNC_BUFFCOUNT		=	0x10000040
SET_DATA_FORMAT				=	0x10000041
GET_DATA_FORMAT				=	0x10000042
DATA_FORMAT_UNSIGNED		=	0
DATA_FORMAT_SIGNED		=		1
SET_SINGLE_CHANNEL_MODE	=		0x10000043
GET_SAMPLES_PER_TIMESTAMP_CLOCK=	0x10000044
GET_RECORDS_CAPTURED		=	0x10000045
GET_MAX_PRETRIGGER_SAMPLES	=	0x10000046
SET_ADC_MODE				=	0x10000047
ECC_MODE					=	0x10000048
ECC_DISABLE				=	0
ECC_ENABLE					=	1
GET_AUX_INPUT_LEVEL		=		0x10000049
AUX_INPUT_LOW				=	0
AUX_INPUT_HIGH				=	1
EXT_TRIGGER_IMPEDANCE		=	0x10000065
EXT_TRIG_50_OHMS			=	0
EXT_TRIG_300_OHMS			=	1
GET_CHANNELS_PER_BOARD	=		0x10000070
GET_CPF_DEVICE				=	0x10000071
PACK_MODE					=	0x10000072
PACK_DEFAULT			=		0
PACK_8_BITS_PER_SAMPLE	=	1
GET_FPGA_TEMPERATURE		=	0x10000080

# gets board specific parameters
MEMORY_SIZE				=		0x1000002A
BOARD_TYPE					=	0x1000002B
ASOPC_TYPE					=	0x1000002C
GET_BOARD_OPTIONS_LOW	=		0x10000037
GET_BOARD_OPTIONS_HIGH=			0x10000038
OPTION_STREAMING_DMA		=	(1 << 0)
OPTION_EXTERNAL_CLOCK		=	(1 << 1)
OPTION_DUAL_PORT_MEMORY	=	(1 << 2)
OPTION_180MHZ_OSCILLATOR=		(1 << 3)
OPTION_LVTTL_EXT_CLOCK	=		(1 << 4)
OPTION_SW_SPI				=	(1 << 5)
OPTION_ALT_INPUT_RANGES=		(1 << 6)
OPTION_VARIABLE_RATE_10MHZ_PLL=	(1 << 7)

# sets and gets
# The transfer offset is defined as the place to start
# the transfer relative to trigger. The value is signed.
# -------TO>>>T>>>>>>>>>TE------------
TRANSFER_OFFET				=	0x10000030
TRANSFER_LENGTH				=	0x10000031 # TO -> TE

# Transfer related constants
TRANSFER_RECORD_OFFSET		=	0x10000032
TRANSFER_NUM_OF_RECORDS		=	0x10000033
TRANSFER_MAPPING_RATIO		=	0x10000034

# only gets
TRIGGER_ADDRESS_AND_TIMESTAMP=	0x10000035

# MASTER/SLAVE CONTROL sets/gets
MASTER_SLAVE_INDEPENDENT	=	0x10000036

# boolean gets
TRIGGERED				=		0x10000040
BUSY						=	0x10000041
WHO_TRIGGERED			=		0x10000042
GET_ASYNC_BUFFERS_PENDING=		0x10000050
GET_ASYNC_BUFFERS_PENDING_FULL=	0x10000051
GET_ASYNC_BUFFERS_PENDING_EMPTY=	0x10000052
ACF_SAMPLES_PER_RECORD		=	0x10000060
ACF_RECORDS_TO_AVERAGE		=	0x10000061
ACF_MODE					=	0x10000062

# *****************************************************************************
#
# 	Constants Used With The Command Set Listed Above
#
#*****************************************************************************

#
# Sample Rate values
#
SAMPLE_RATE_1KSPS	=	0X00000001
SAMPLE_RATE_2KSPS	=	0X00000002
SAMPLE_RATE_5KSPS	=	0X00000004
SAMPLE_RATE_10KSPS	=	0X00000008
SAMPLE_RATE_20KSPS	=	0X0000000A
SAMPLE_RATE_50KSPS	=	0X0000000C
SAMPLE_RATE_100KSPS=		0X0000000E
SAMPLE_RATE_200KSPS=		0X00000010
SAMPLE_RATE_500KSPS=		0X00000012
SAMPLE_RATE_1MSPS	=	0X00000014
SAMPLE_RATE_2MSPS	=	0X00000018
SAMPLE_RATE_5MSPS	=	0X0000001A
SAMPLE_RATE_10MSPS	=	0X0000001C
SAMPLE_RATE_20MSPS	=	0X0000001E
SAMPLE_RATE_25MSPS	=	0X00000021
SAMPLE_RATE_50MSPS	=	0X00000022
SAMPLE_RATE_100MSPS=		0X00000024
SAMPLE_RATE_125MSPS=		0x00000025
SAMPLE_RATE_160MSPS=		0x00000026
SAMPLE_RATE_180MSPS=		0x00000027
SAMPLE_RATE_200MSPS=		0X00000028
SAMPLE_RATE_250MSPS=		0X0000002B
SAMPLE_RATE_400MSPS=		0X0000002D
SAMPLE_RATE_500MSPS=		0X00000030
SAMPLE_RATE_800MSPS=		0X00000032
SAMPLE_RATE_1000MSPS=	0x00000035
SAMPLE_RATE_1GSPS	=	SAMPLE_RATE_1000MSPS
SAMPLE_RATE_1200MSPS=	0x00000037
SAMPLE_RATE_1500MSPS=	0x0000003A
SAMPLE_RATE_1600MSPS=	0x0000003B
SAMPLE_RATE_1800MSPS=	0x0000003D
SAMPLE_RATE_2000MSPS=	0x0000003F
SAMPLE_RATE_2GSPS	=	SAMPLE_RATE_2000MSPS

# user define sample rate - used with External Clock
SAMPLE_RATE_USER_DEF	=0x00000040
# ATS665 Specific Setting for using the PLL
#
# The base value can be used to create a PLL frequency
# in a simple manner.
#
# Ex.
#        105 MHz = PLL_10MHZ_REF_100MSPS_BASE + 5000000
#        120 MHz = PLL_10MHZ_REF_100MSPS_BASE + 20000000
PLL_10MHZ_REF_100MSPS_BASE=	0x05F5E100

# ATS665 Specific Decimation constants
DECIMATE_BY_8		=	0x00000008
DECIMATE_BY_64	=		0x00000040

#
# Impedance Values
#
IMPEDANCE_1M_OHM	=	0x00000001
IMPEDANCE_50_OHM	=	0x00000002
IMPEDANCE_75_OHM	=	0x00000004
IMPEDANCE_300_OHM	=	0x00000008

#
#Clock Source
#
INTERNAL_CLOCK		=	0x00000001
EXTERNAL_CLOCK		=	0x00000002
FAST_EXTERNAL_CLOCK=		0x00000002
MEDIMUM_EXTERNAL_CLOCK=	0x00000003 #TYPO
MEDIUM_EXTERNAL_CLOCK=	0x00000003
SLOW_EXTERNAL_CLOCK	=	0x00000004
EXTERNAL_CLOCK_AC		=0x00000005
EXTERNAL_CLOCK_DC		=0x00000006
EXTERNAL_CLOCK_10MHz_REF= 0x00000007
INTERNAL_CLOCK_DIV_5=	0x000000010
MASTER_CLOCK		=	0x000000011
INTERNAL_CLOCK_SET_VCO=	0x000000012

#
# Clock Edge
#
CLOCK_EDGE_RISING	=	0x00000000
CLOCK_EDGE_FALLING	=	0x00000001

#
# Input Ranges
#
INPUT_RANGE_PM_20_MV =0x00000001
INPUT_RANGE_PM_40_MV =0x00000002
INPUT_RANGE_PM_50_MV =0x00000003
INPUT_RANGE_PM_80_MV =0x00000004
INPUT_RANGE_PM_100_MV=	0x00000005
INPUT_RANGE_PM_200_MV=	0x00000006
INPUT_RANGE_PM_400_MV=	0x00000007
INPUT_RANGE_PM_500_MV=	0x00000008
INPUT_RANGE_PM_800_MV	=0x00000009
INPUT_RANGE_PM_1_V	=	0x0000000A
INPUT_RANGE_PM_2_V	=	0x0000000B
INPUT_RANGE_PM_4_V	=	0x0000000C
INPUT_RANGE_PM_5_V	=	0x0000000D
INPUT_RANGE_PM_8_V	=	0x0000000E
INPUT_RANGE_PM_10_V=		0x0000000F
INPUT_RANGE_PM_20_V=		0x00000010
INPUT_RANGE_PM_40_V=		0x00000011
INPUT_RANGE_PM_16_V=		0x00000012
INPUT_RANGE_HIFI	=	0x00000020
INPUT_RANGE_PM_1_V_25=	0x00000021
INPUT_RANGE_PM_2_V_5=	0x00000025
INPUT_RANGE_PM_125_MV=	0x00000028
INPUT_RANGE_PM_250_MV	=0x00000030

#
# Coupling Values
#
AC_COUPLING		=		0x00000001
DC_COUPLING		=		0x00000002

#
# Trigger Engines
#
TRIG_ENGINE_J		=	0x00000000
TRIG_ENGINE_K		=	0x00000001

#
# Trigger Engine Operation
#
TRIG_ENGINE_OP_J		=	0x00000000
TRIG_ENGINE_OP_K		=	0x00000001
TRIG_ENGINE_OP_J_OR_K	=	0x00000002
TRIG_ENGINE_OP_J_AND_K=		0x00000003
TRIG_ENGINE_OP_J_XOR_K	=	0x00000004
TRIG_ENGINE_OP_J_AND_NOT_K=	0x00000005
TRIG_ENGINE_OP_NOT_J_AND_K=	0x00000006

#
# Trigger Engine Sources
#
TRIG_CHAN_A		=		0x00000000
TRIG_CHAN_B		=		0x00000001
TRIG_EXTERNAL		=	0x00000002
TRIG_DISABLE		=	0x00000003
TRIG_CHAN_C		=		0x00000004
TRIG_CHAN_D		=		0x00000005

#
# Trigger Slope
#
TRIGGER_SLOPE_POSITIVE=	0x00000001
TRIGGER_SLOPE_NEGATIVE=	0x00000002

#
# Channel Selection
#
CHANNEL_ALL		=		0x00000000
CHANNEL_A			=	0x00000001
CHANNEL_B			=	0x00000002
CHANNEL_C			=	0x00000004
CHANNEL_D			=	0x00000008
CHANNEL_E			=	0x00000010
CHANNEL_F			=	0x00000020
CHANNEL_G			=	0x00000040
CHANNEL_H			=	0x00000080

#
# Master/Slave Configuration
#
BOARD_IS_INDEPENDENT=	0x00000000
BOARD_IS_MASTER		=	0x00000001
BOARD_IS_SLAVE		=	0x00000002
BOARD_IS_LAST_SLAVE=		0x00000003

#
# LED Control
#
LED_OFF		=			0x00000000
LED_ON		=			0x00000001

#
# Attenuator Relay
#
AR_X1				=	0x00000000
AR_DIV40		=		0x00000001

#
# External Trigger Attenuator Relay
#
ETR_DIV5		=		0x00000000
ETR_X1			=		0x00000001
ETR_5V			=		0x00000000
ETR_1V			=		0x00000001
ETR_TTL			=		0x00000002
ETR_2V5			=		0x00000003

#
# Device Sleep state
#
POWER_OFF		=		0x00000000
POWER_ON		=		0x00000001

#
# Software Events control
#
SW_EVENTS_OFF		=	0x00000000
SW_EVENTS_ON		=	0x00000001

#
# TimeStamp Value Reset Control
#
TIMESTAMP_RESET_FIRSTTIME_ONLY=	0x00000000
TIMESTAMP_RESET_ALWAYS		=	0x00000001

# DAC Names used by API AlazarDACSettingAdjust
#
# DAC Names Specific to the ATS460
#
ATS460_DAC_A_GAIN		=	0x00000001
ATS460_DAC_A_OFFSET	=		0x00000002
ATS460_DAC_A_POSITION	=	0x00000003
ATS460_DAC_B_GAIN		=	0x00000009
ATS460_DAC_B_OFFSET	=		0x0000000A
ATS460_DAC_B_POSITION	=	0x0000000B
ATS460_DAC_EXTERNAL_CLK_REF=	0x00000007
#
# DAC Names Specific to the ATS660
#
ATS660_DAC_A_GAIN		=	0x00000001
ATS660_DAC_A_OFFSET	=		0x00000002
ATS660_DAC_A_POSITION	=	0x00000003
ATS660_DAC_B_GAIN		=	0x00000009
ATS660_DAC_B_OFFSET	=		0x0000000A
ATS660_DAC_B_POSITION	=	0x0000000B
ATS660_DAC_EXTERNAL_CLK_REF=	0x00000007
#
# DAC Names Specific to the ATS665
#
ATS665_DAC_A_GAIN		=	0x00000001
ATS665_DAC_A_OFFSET	=		0x00000002
ATS665_DAC_A_POSITION	=	0x00000003
ATS665_DAC_B_GAIN		=	0x00000009
ATS665_DAC_B_OFFSET	=		0x0000000A
ATS665_DAC_B_POSITION	=	0x0000000B
ATS665_DAC_EXTERNAL_CLK_REF=	0x00000007
# DAC Names Specific to the ATS860
#  ------------ Not implemented yet ---------
# DAC Names Specific to the ATS310
#  ------------ Not implemented yet ---------
# DAC Names Specific to the ATS330
#  ------------ Not implemented yet ---------
# DAC Names Specific to the ATS850
#  ------------ Not implemented yet ---------
#
# Error return values
#
SETDAC_INVALID_SETGET	= 660
SETDAC_INVALID_CHANNEL=   661
SETDAC_INVALID_DACNAME	= 662
SETDAC_INVALID_COUPLING  =663
SETDAC_INVALID_RANGE	= 664
SETDAC_INVALID_IMPEDANCE= 665
SETDAC_BAD_GET_PTR      = 667
SETDAC_INVALID_BOARDTYPE = 668

CSO_DUMMY_CLOCK_DISABLE	=	0
CSO_DUMMY_CLOCK_TIMER	=	1
CSO_DUMMY_CLOCK_EXT_TRIGGER=	2
CSO_DUMMY_CLOCK_TIMER_ON_TIMER_OFF=	3

#
# Auxilary IO
#
AUX_OUT_TRIGGER			=		0
AUX_OUT_PACER				=	2
AUX_OUT_BUSY				=	4
AUX_OUT_CLOCK				=	6
AUX_OUT_RESERVED		=		8
AUX_OUT_CAPTURE_ALMOST_DONE	=	10
AUX_OUT_AUXILIARY		=		12
AUX_OUT_SERIAL_DATA	=			14
AUX_OUT_TRIGGER_ENABLE=			16

AUX_IN_TRIGGER_ENABLE		=	1
AUX_IN_DIGITAL_TRIGGER	=		3
AUX_IN_GATE					=	5
AUX_IN_CAPTURE_ON_DEMAND=		7
AUX_IN_RESET_TIMESTAMP	=		9
AUX_IN_SLOW_EXTERNAL_CLOCK=		11
AUX_IN_AUXILIARY			=	13
AUX_IN_SERIAL_DATA			=	15

AUX_INPUT_AUXILIARY		=		AUX_IN_AUXILIARY
AUX_INPUT_SERIAL_DATA		=	AUX_IN_SERIAL_DATA

# AlazarSetExternalTriggerOperationForScanning

STOS_OPTION_DEFER_START_CAPTURE=	1

# Data skipping

SSM_DISABLE	=	0
SSM_ENABLE		=1

# Coprocessor

CPF_REG_SIGNATURE	=	0
CPF_REG_REVISION	=	1
CPF_REG_VERSION		=	2
CPF_REG_STATUS		=	3

CPF_OPTION_DMA_DOWNLOAD	=	1

CPF_DEVICE_UNKNOWN	=	0
CPF_DEVICE_EP3SL50	=	1
CPF_DEVICE_EP3SE260=		2
