import sys, os
from os import path
import struct
from socket import *
import numpy as np
import time
import datetime
import threading

class UDPSocketClient:
    def __init__(self, ip=None):
        self.mHost = '192.168.1.151'  if ip is None else ip
        #self.mHost = '127.0.0.1'
        self.mPort = 6000
        self.mBufSize = _gSocketBodySize + _gSocketHeaderSize
        self.mAddress = (self.mHost, self.mPort)
        self.mUDPClient = socket(AF_INET, SOCK_DGRAM)
       # self.mUDPClient.bind(("",7788))
        self.mData = None
        self.mUDPClient.settimeout(5)

    def setBufSize (self,  bufSize):
        self.mBufSize = bufSize

    def sendData(self):
        self.mUDPClient.sendto(self.mData,self.mAddress)
        self.mData = None # Clear data after send out

    def receiveData(self):
       self.mData, self.mAddress = self.mUDPClient.recvfrom(_gSocketBodySize + _gSocketHeaderSize)
       return self.mData

# Send Command
def _sendcommand(cmdid,status,msgid,len,type,offset,apiversion,pad,CRC16,cmdData):
    cmdid=struct.pack('H',htons(cmdid))
    status=struct.pack('H',htons(status))
    msgid=struct.pack('H',htons(msgid))
    len=struct.pack('H',htons(len))
    type=struct.pack('H',htons(type))
    offset=struct.pack('H',htons(offset))
    apiversion=struct.pack('B',apiversion) # 1 Byte unsigned char
    pad=struct.pack('B',pad) # 1 Byte unsigned char
    CRC16=struct.pack('H',htons(CRC16)) # 2 Byte unsigned short
    cmdHeader = cmdid + status + msgid + len + type + offset + apiversion + pad + CRC16

    if (cmdData != None):
        _gUDPSocketClient.mData = cmdHeader + cmdData
    else:
        _gUDPSocketClient.mData = cmdHeader

    _gUDPSocketClient.sendData()

def sendCmdRDReg(regAddress, regValue):
  socketBodySize = 8
  _gUDPSocketClient.setBufSize(socketBodySize + _gSocketHeaderSize)
  cmdData = struct.pack('L', htonl(regAddress)) +  struct.pack('L', htonl(regValue))
  _sendcommand(0x5a01,0x0000,0x5a01,0x0008,0x0000,0x0000,0x00,0x00,0x0000, cmdData)

# Send Write Register Command
def sendCmdWRReg(regAddress, regValue):
  socketBodySize = 8
  _gUDPSocketClient.setBufSize(socketBodySize + _gSocketHeaderSize)
  cmdData = struct.pack('L', htonl(regAddress)) +  struct.pack('L', htonl(regValue))
  _sendcommand(0x5a02,0x0000,0x5a02,0x0008,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
  _gUDPSocketClient.receiveData() # Do nothing

# Get Sample Rate
def getSampleRate():
    socketBodySize = 4
    _gUDPSocketClient.setBufSize(socketBodySize + _gSocketHeaderSize)
    # Len is not cared
    _sendcommand(0x5a0a,0x0000,0x5a0a,0x0004,0x0000,0x0000,0x00,0x00,0x0000, None )
    data = _gUDPSocketClient.receiveData()
    value = ntohl(int(struct.unpack('L',data[16:20])[0]))

    if (value == 0):
      value = 500
    elif (value == 1):
      value = 1000
    elif (value == 2):
      value = 1250
    elif (value == 3):
      value = 400

    return value

# Set Sample Rate: 500/1000/1250/400 corresponding to 0/1/2/3
def setSampleRate(sampleRate):
    sampleRate = int(sampleRate)
    global _gSampleRate
    _gSampleRate = sampleRate
    if (sampleRate == 500):
      value = 0
    elif (sampleRate == 1000):
      value = 1
    elif (sampleRate == 1250):
      value = 2
    elif (sampleRate == 400):
      value = 3

    socketBodySize = 4
    _gUDPSocketClient.setBufSize(socketBodySize + _gSocketHeaderSize)
    cmdData = struct.pack('L', htonl(value))
    _sendcommand(0x5a09,0x0000,0x5a09,0x0004,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
    _gUDPSocketClient.receiveData() # Do nothing

def getTriggerType():
    sendCmdRDReg(0x02, 0x00)
    data = _gUDPSocketClient.receiveData()
    value = ntohl(int(struct.unpack('L',data[20:24])[0]))
    return value

def getReadDataCount():
    sendCmdRDReg(0x10,0x00)
    data = _gUDPSocketClient.receiveData()
    data = data[20:24]
    lowValue = ntohl(int(struct.unpack('L',data)[0]))
    # print ("0x10 Value:",  hex(lowValue))
    sendCmdRDReg(0x12,  0x00)
    data = _gUDPSocketClient.receiveData()
    data = data[20:24]
    highValue =ntohl(int(struct.unpack('L',data)[0]))
    # print ("0x12 Value:",  hex(highValue))
    value = highValue << 16 | lowValue
    return value
    #return 1024

# Set Trigger Type, 0: Auto, 1: External
def setTriggerType(triggerType):
    global _gTriggerType
    _gTriggerType = triggerType

    regAddr= 0x2 # 0x2, Bit[2], 0: Auto, 1: External
    if triggerType == 0: # Auto Trigger
        mask = 0b1111111111111011
        currentValue = triggerType & mask
    elif triggerType == 1: # External
        mask = 0b100
        currentValue = triggerType | mask

    sendCmdWRReg(regAddr, currentValue)

# Set Ref Clock, 0: Internal, 1: External
def setRefClock(clockType):
    clockType = eval(clockType)
    if (clockType == 0): # Internal Clock
      sendCmdWRReg(0x2,  0x20)
      sendCmdWRReg(0x2,  0x28)
      sendCmdWRReg(0x2,  0x29)
      sendCmdWRReg(0x2,  0x2b)
    else: # External Clock
      sendCmdWRReg(0x2,  0x10)
      sendCmdWRReg(0x2,  0x18)
      sendCmdWRReg(0x2,  0x19)
      sendCmdWRReg(0x2,  0x1b)

# Set Frame Mode(True:False)
def setFrameMode(frameModel):
    global _gFrameModel
    _gFrameModel = frameModel

# Set Frame Number
def setFrameNumber(frameNum):
    global _gFrameNumber
    _gFrameNumber = frameNum

    if (frameNum <= 2**16-1):
      regAddr= 0x4
      regValue= frameNum
      sendCmdWRReg(regAddr,  regValue)
    else:
       # Low
      regAddr= 0x4
      regValue= frameNum & (2**16-1)
      sendCmdWRReg(regAddr,  regValue)
      # High
      regAddr= 0x6
      regValue= frameNum >> 16
      sendCmdWRReg(regAddr,  regValue)

# Set Record Length(Unit(1k) like 1,2,4,8,16,32...)
def setRecordLength(recordLength):
    global _gRecordLength
    _gRecordLength = recordLength
    regAddr= 0x8
    regValue= recordLength
    sendCmdWRReg(regAddr,regValue)

# Time Stamp in millseconds
def getTimeStamp():
    ct = time.time()
    local_time = time.localtime(ct)
    data_head = time.strftime("%Y-%m-%d-%H-%M-%S", local_time)
    data_secs = (ct - int(ct)) * 1000
    time_stamp = "%s-%03d" % (data_head, data_secs)
    return time_stamp

# Bu ma to Yuan ma
def bumatoyuanma(x):
    if (x > 32767):
       x = x - 65536
    return x

def parseADSampleData(data, length, withHead):
    data_ChA = []
    data_ChB = []
    if (withHead):
      data = data[16:]
    else:
      data = data

    offsetA = 42-23.5
    offsetB = -8+49-134
    maxVolA = 1.485
    maxVolB = 1.698

    for pos in range(0, length*1024, 4):
      line = data[pos:pos+4]
      if (len(line) == 4):
          data_ChA.append(1000*(bumatoyuanma(ntohs(struct.unpack('H',line[0:2])[0]))+offsetA)*maxVolA/65536)
          data_ChB.append(1000*(bumatoyuanma(ntohs(struct.unpack('H',line[2:4])[0]))+offsetB)*maxVolB/65536)

    return [data_ChA, data_ChB]

# send command to capture data
def sendCmdRAW_AD_SAMPLE(length):
    socketBodySize = length*1024
    _gUDPSocketClient.setBufSize(socketBodySize + _gSocketHeaderSize)
    _sendcommand(0x5a04,0x0000,0x5a04,length*1024,0x0000,0x0000,0x00,0x00,0x0000, None)

# Receive captured data
def receiveCmdRAW_AD_SAMPLE(length):
    socketBodySize = length*1024
    _gUDPSocketClient.setBufSize(socketBodySize + _gSocketHeaderSize)
    _gUDPSocketClient.receiveData()
    # print ("Receive Total Length:",  len(_gUDPSocketClient.mData))
    return _gUDPSocketClient.mData

# Call this to when starting to capture data
def startCapture():
    if (_gTriggerType == 0): # Auto
      sendCmdWRReg(0x2, 0x28) # Reset
      sendCmdWRReg(0x2, 0x29) # Start to capture
    else: # External
      sendCmdWRReg(0x2, 0x2c) # Reset
      sendCmdWRReg(0x2, 0x2d) # Start to capture

# Read data from socket
def readSocketData(length):
    sendCmdRAW_AD_SAMPLE(length * 4)
    return receiveCmdRAW_AD_SAMPLE(length * 4)

# Capture data in Non-Frame Mode
def captureNonFrameMode(length):
    data_ChA = []
    data_ChB = []
    receiveTimes = int(length / 8)
    lastTimeLength = length % 8
    withHead = True
    expectLength = length * 1024
    while (True):
      currentDataLength = getReadDataCount()
      if (expectLength <= currentDataLength):
          if (_gTriggerType == 0): # Auto
              sendCmdWRReg(0x2, 0x2b) # Start to read
          else:
              sendCmdWRReg(0x2, 0x2f) # Start to read

          if receiveTimes <= 1:
              data = readSocketData(length * 4)
              if data:
                  data = parseADSampleData(data, length * 4, withHead)
                  data_ChA = data[0]
                  data_ChB = data[1]
                  break # Stop for this time
          else:
              for loop in range(0, receiveTimes):
                data = readSocketData(32)
                if data:
                  data = parseADSampleData(data, 32, withHead)
                  data_ChA = data_ChA + data[0]
                  data_ChB = data_ChB + data[1]
              if (lastTimeLength > 0):
                data = getData(lastTimeLength*4)
                if data:
                  data = parseADSampleData(data, lastTimeLength*4, withHead)
                  data_ChA = data_ChA + data[0]
                  data_ChB = data_ChB + data[1]
              break; # Stop for this time
      else:
          time.sleep(0.1) # Sleep for a while to wait the expectLength

    return [data_ChA, data_ChB]


# Capture data in Frame Mode
def captureFrameMode(length, frameNum):
    data_ChA_List = []
    data_ChB_List = []
    receiveTimes = int (length / 8)
    lastTimeLength = length % 8
    withHead = True

    expectLength = length * 1024
    while (True):
      currentDataLength = getReadDataCount()
      if (expectLength <= currentDataLength):
          if (_gTriggerType == 0): # Auto
              sendCmdWRReg(0x2, 0x2b) # Start to read
          else:
              sendCmdWRReg(0x2, 0x2f) # Start to read

          data_ChA = []
          data_ChB = []
          for frameIndex in range(1,  frameNum + 1):
              data_ChA = []
              data_ChB = []
              if receiveTimes <= 1:
                data = readSocketData(length * 4)
                if data:
                    # print ("Receive Total Length:",  len(data))
                    data = parseADSampleData(data, length * 4, withHead)
                    data_ChA = data[0]
                    data_ChB = data[1]
                    data_ChA_List.append(data_ChA)
                    data_ChB_List.append(data_ChB)
              else:
                  data_ChA = []
                  data_ChB = []
                  for loop in range(0, receiveTimes):
                      data = readSocketData(32)
                      if data:
                          data = parseADSampleData(data, 32,  withHead)
                          data_ChA = data_ChA + data[0]
                          data_ChB = data_ChB + data[1]
                  # Save for the last frame
                  if (lastTimeLength > 0):
                      data = readSocketData(lastTimeLength*4)
                      if data:
                          data = parseADSampleData(data, lastTimeLength*4, withHead)
                          data_ChA = data_ChA + data[0]
                          data_ChB = data_ChB + data[1]

                  data_ChA_List.append(data_ChA)
                  data_ChB_List.append(data_ChB)
          break # Break for this time
      else:
          time.sleep(0.1) # Sleep for a while to wait the expectLength

    return [data_ChA_List, data_ChB_List]

# Get Data, if frameNum > 1, then it is in FrameMode
def getData():
  length = _gRecordLength
  frameNum = _gFrameNumber
  if (frameNum < 1):
    print("Incorrect Frame Number: %s" % str(frameNum))
    data = None
  elif (frameNum == 1):
    data = captureNonFrameMode(length)
  elif (frameNum > 1):
    data = captureFrameMode(length, frameNum)

  return data

# Rest FPGA to be ready to capture data
def resetFPGA():
    if (getTriggerType() == 0):
      sendCmdWRReg(0x2,  0x20)
      sendCmdWRReg(0x2,  0x28)
    else:
      sendCmdWRReg(0xa,  0x0)
      sendCmdWRReg(0x2,  0x2c)
      sendCmdWRReg(0x2,  0x2d)

# Initialize...
def Initialize():
  resetFPGA()

_gSocketHeaderSize = 16
_gSocketBodySize = 32 * 1024
_gSocketBufSize = _gSocketBodySize + _gSocketHeaderSize

_gUDPSocketClient = UDPSocketClient(ip=None)
_gFrameNumber = 1
_gRecordLength = 1 # Unit is 1024(1k)
_gTriggerType = 0  # 0: Auto, 1, External
_gSampleRate = 1000 # Unit is M/s
_gFrameMode = False
