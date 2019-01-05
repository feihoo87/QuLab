# -*- coding: utf-8 -*-

"""
Module implementing VoltageSettingDialog.
"""
import sys
import struct
from socket import *


gDMax = 2**20-1
gDMin = 0
gVolMax = 10
gVolMin = -10

class UDPSocketClient:
    def __init__(self):
        self.mHost = '192.168.1.6'
        #self.mHost = '127.0.0.1'
        self.mPort = 6000
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
       self.mData, self.mAddress = self.mUDPClient.recvfrom(self.mBufsize)
       return self.mData


class Voltage():
    """
    Class documentation goes here.
    """
    def __init__(self):
        """
        Constructor

        @param parent reference to the parent widget
        @type QWidget
        """
        self.udpSocketClient = UDPSocketClient()
        # self.dValue = 0.0
        self.volValue = 1.0

        # Set channel 1 as default
        self.sendCmdChnnelNum(0)

    def sendcommand(self, cmdid, status, msgid, len, type, offset, apiversion, pad, CRC16,  cmdData):
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
           self.udpSocketClient.mData = cmdHeader + cmdData
        else:
           self.udpSocketClient.mData = cmdHeader

        self.udpSocketClient.sendData()

    def writeReg(self,value):
       # hex(int("0x0001", 16)),hex(self.dValue )
        # cmdData  =  struct.pack('L', htonl(1))  + struct.pack('L', htonl(self.dValue))
        dValue=round((value-gVolMin)*(2**20-1)/(gVolMax-gVolMin))
        cmdData  =  struct.pack('L', htonl(1))  + struct.pack('L', htonl(dValue))
        self.sendcommand(0x5a02,0x0000,0x5a02,0x0008,0x0000,0x0000,0x00,0x00,0x0000, cmdData)

    def calVol(self,  dValue):
         self.volValue = round(((gVolMax-gVolMin)*dValue/(2**20-1) + gVolMin), 6)
         self.lineEdit_Vol.setText(str(self.volValue))

    def sendCmdChnnelNum(self,  value):
        # set the data length to 4
        self.udpSocketClient.setBufSize(4 + 16);

        cmdData  =  struct.pack('L', htonl(value))
        self.sendcommand(0x5a09,0x0000,0x5a09,0x0004,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
        self.udpSocketClient.receiveData() # Do nothing
        # set back the data length to 8
        self.udpSocketClient.setBufSize(8+ 16);

def setvol(vol=0,ch=0):
    a=Voltage()
    a.sendCmdChnnelNum(ch)
    a.writeReg(vol)

if __name__ == '__main__':
    a=Voltage()
    a.sendCmdChnnelNum(1)
    a.writeReg(0.5)
    # b =
