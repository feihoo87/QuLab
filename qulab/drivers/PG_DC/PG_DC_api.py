# -*- coding: utf-8 -*-

"""
Module implementing VoltageSettingDialog.
"""
import sys
import struct
from socket import *
import numpy as np

gDMax = 2**20-1
gDMin = 0
gVolMax = 10
gVolMin = -10

class UDPSocketClient:
    def __init__(self, ip=None, port=None):
        self.mHost = '192.168.1.6' if ip is None else ip

        self.mPort = 6000 if port is None else port
        self.mBufsize = 8 + 16
        self.mAddress = (self.mHost, self.mPort)
        self.mUDPClient = socket(AF_INET, SOCK_DGRAM)
        self.mData = None
        self.mUDPClient.settimeout(5)

    def sendData(self):
        self.mUDPClient.sendto(self.mData,self.mAddress)

    def setBufSize (self,  bufSize):
        self.mBufSize = bufSize

    def receiveData(self):
       self.mData  = None
       try:
           self.mData, self.mAddress = self.mUDPClient.recvfrom(self.mBufsize)
       except BaseException as e:
           ctypes.windll.user32.MessageBoxA(0, ("Failed to Connect IP: " + self.mHost) .encode('gb2312'), 'Error'.encode('gb2312'),0)
       return self.mData

    def setIP(self, IP):
        self.mHost = str(IP)
        self.mAddress = (self.mHost, self.mPort)

    def setPort(self, port):
        self.mPort =  int(port)
        self.mAddress = (self.mHost, self.mPort)

    def setAddress(self, IP,  port):
        self.mHost = str(IP)
        self.mPort = int(port)
        self.mAddress = (self.mHost, self.mPort)


# class Voltage():
#     """
#     Class documentation goes here.
#     """
#     def __init__(self, ip = None):
#
#         self.udpSocketClient = UDPSocketClient(ip)
#         # self.dValue = 0.0
#         self.volValue = 1.0
#
#         # Set channel 1 as default
#         self.sendCmdChnnelNum(0)
#
#     def sendcommand(self, cmdid, status, msgid, len, type, offset, apiversion, pad, CRC16,  cmdData):
#         cmdid=struct.pack('H',htons(cmdid))
#         status=struct.pack('H',htons(status))
#         msgid=struct.pack('H',htons(msgid))
#         len=struct.pack('H',htons(len))
#         type=struct.pack('H',htons(type))
#         offset=struct.pack('H',htons(offset))
#         apiversion=struct.pack('B',apiversion) # 1 Byte unsigned char
#         pad=struct.pack('B',pad) # 1 Byte unsigned char
#         CRC16=struct.pack('H',htons(CRC16)) # 2 Byte unsigned short
#         cmdHeader = cmdid + status + msgid + len + type + offset + apiversion + pad + CRC16
#
#         if (cmdData != None):
#            self.udpSocketClient.mData = cmdHeader + cmdData
#         else:
#            self.udpSocketClient.mData = cmdHeader
#
#         self.udpSocketClient.sendData()
#
#     def writeReg(self,value):
#        # hex(int("0x0001", 16)),hex(self.dValue )
#         # cmdData  =  struct.pack('L', htonl(1))  + struct.pack('L', htonl(self.dValue))
#         dValue=int(np.around((value-gVolMin)*(2**20-1)/(gVolMax-gVolMin)))
#         cmdData  =  struct.pack('L', htonl(1))  + struct.pack('L', htonl(dValue))
#         self.sendcommand(0x5a02,0x0000,0x5a02,0x0008,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
#
#     def calVol(self,  dValue):
#          self.volValue = round(((gVolMax-gVolMin)*dValue/(2**20-1) + gVolMin), 6)
#          self.lineEdit_Vol.setText(str(self.volValue))
#
#     def sendCmdChnnelNum(self,  value):
#         # set the data length to 4
#         self.udpSocketClient.setBufSize(4 + 16);
#
#         cmdData  =  struct.pack('L', htonl(value))
#         self.sendcommand(0x5a09,0x0000,0x5a09,0x0004,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
#         self.udpSocketClient.receiveData() # Do nothing
#         # set back the data length to 8
#         self.udpSocketClient.setBufSize(8+ 16);
#
#     def setVoltage(self,voltage=0,ch=0):
#         self.sendCmdChnnelNum(ch)
#         self.writeReg(voltage)

class Voltage():
    """
    Class documentation goes here.
    """

    gDMax = 2**20-1
    gDMin = 0
    gVolMax = 10
    gVolMin = -10

    def __init__(self, ip = None, port=None):

        self.gUDPSocketClient = UDPSocketClient(ip, port)
        # # self.dValue = 0.0
        # self.volValue = 1.0
        #
        # # Set channel 1 as default
        self.SetChannelNum(0,0)

    def SetPort(self, port):
        self.gUDPSocketClient.setPort(port)

    def Sendcommand(self, cmdid, status, msgid, len, type, offset, apiversion, pad, CRC16, cmdData):
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
           self.gUDPSocketClient.mData = cmdHeader + cmdData
        else:
           self.gUDPSocketClient.mData = cmdHeader

        self.gUDPSocketClient.sendData()

    def WriteReg(self,dValue):
       # hex(int("0x0001", 16)),hex(self.dValue )
        cmdData  =  struct.pack('L', htonl(1))  + struct.pack('L', htonl(int(dValue)))
        self.Sendcommand(0x5a02,0x0000,0x5a02,0x0008,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
        self.gUDPSocketClient.receiveData() # Do nothing

    def SetDValue(self,dValue):
        if(dValue  >= gDMax):
           dValue  = gDMax
        elif(dValue  <= gDMin):
           dValue  = gDMin
        self.WriteReg(dValue)

    def setVoltage(self,voltage=0,ch=0):
        self.SetChannelNum(ch,0)
        self.SetDValue(self.CalculateDValue(voltage))

    def CalculateVoltage(self,dValue):
        if(dValue >= gDMax):
           dValue = gDMax
        elif(dValue <= gDMin):
           dValue = gDMin

        volValue = round(((self.gVolMax-self.gVolMin)*dValue/(2**20-1) + self.gVolMin), 6)
        return volValue

    def CalculateDValue(self,volValue):
        dValue = round((volValue-self.gVolMin)*(2**20-1)/(self.gVolMax-self.gVolMin))
        return dValue

    def SetChannelNum(self,channelNum, initialized=0):
        # set the data length to 4
        self.gUDPSocketClient.setBufSize(4 + 16);
        cmdData  =  struct.pack('2B', 0, 0)  + struct.pack('B', initialized)  + struct.pack('B', channelNum)
        self.Sendcommand(0x5a09,0x0000,0x5a09,0x0004,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
        data = self.gUDPSocketClient.receiveData()
        # Do nothing
        # set back the data length to 8
        self.gUDPSocketClient.setBufSize(8+ 16)
        if (data != None):
            return True
        else:
            return False

    def SetNewIP(self,IP):
        # set the data length to 4
        self.gUDPSocketClient.setBufSize(4 + 16);
        # Convert IP str to int32
        packedIP = socket.inet_aton(IP)
        ipAddr = struct.unpack("L", packedIP)[0] # !	network (= big-endian)
        cmdData  =  struct.pack('L', ipAddr)
        self.Sendcommand(0xd0e1,0x0000,0xd0e1,0x0004,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
        # set back the data length to 8
        self.gUDPSocketClient.setBufSize(8+16)
        self.gUDPSocketClient.setIP(IP)

    def SetDefaultIP(self,IP):
        self.gUDPSocketClient.setIP(IP)

    def SetVolMax(self,volMax):
        self.gVolMax = volMax

    def SetVolMin(self,volMin):
        self.gVolMin = volMin
