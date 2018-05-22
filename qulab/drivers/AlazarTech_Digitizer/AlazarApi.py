# -*- coding: utf-8 -*-
import logging
logger = logging.getLogger('qulab.drivers.ATS')
logger.setLevel(logging.DEBUG)

logger.debug('ATS driver start loading APIs ...')

import ctypes, os
from ctypes import (c_int8, c_uint8, c_int16, c_uint16, c_int64, c_uint64,
                    c_char_p, c_wchar_p, c_void_p, c_long, c_ulong,
                    c_int, c_uint, c_float, byref, Structure, POINTER)

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
    sPath = os.path.dirname(os.path.abspath(__file__))
    logger.debug('Loading ATSApi.dll in driver folder : %s ...', sPath)
    DLL = ctypes.CDLL(os.path.join(sPath, 'ATSApi'))
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
    func = getattr(DLL, funcname)
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
