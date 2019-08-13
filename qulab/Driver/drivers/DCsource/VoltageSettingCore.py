# -*- coding: utf-8 -*-

"""
Module implementing VoltageSettingDialog.
"""
import sys,  os
from os import path 
import struct
from socket import * 
import socket
import ctypes
import time


gDMax = 2**20-1
gDMin = 0
gVolMax = 10
gVolMin = -10

class UDPSocketClient:
    def __init__(self, IP, Port):
        self.mHost = IP
        if (self.mHost == None):
           self.mHost = '192.168.1.6'
        #self.mHost = '127.0.0.1'
        self.mPort = Port 
        if (self.mPort == None):
           self.mPort = 6000
           
        self.mBufsize = 8 + 16 
        self.mAddress = (self.mHost, self.mPort)
        self.mUDPClient = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #self.mUDPClient.bind(("",7788))
        self.mData = None
        self.mUDPClient.settimeout(2)

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
    
def SetPort(port):
    gUDPSocketClient.setPort(port)
    
def Sendcommand(cmdid, status, msgid, len, type, offset, apiversion, pad, CRC16, cmdData):
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
       gUDPSocketClient.mData = cmdHeader + cmdData
    else:
       gUDPSocketClient.mData = cmdHeader
  
    gUDPSocketClient.sendData()

def WriteReg(dValue):  
   # hex(int("0x0001", 16)),hex(self.dValue )
    cmdData  =  struct.pack('L', htonl(1))  + struct.pack('L', htonl(int(dValue))) 
    Sendcommand(0x5a02,0x0000,0x5a02,0x0008,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
    gUDPSocketClient.receiveData() # Do nothing

def SetDValue(dValue): 
    if(dValue  >= gDMax):
       dValue  = gDMax
    elif(dValue  <= gDMin):
       dValue  = gDMin
    WriteReg(dValue)
    
def CalculateVoltage(dValue):
    if(dValue >= gDMax):
       dValue = gDMax
    elif(dValue <= gDMin):
       dValue = gDMin
       
    volValue = round(((gVolMax-gVolMin)*dValue/(2**20-1) + gVolMin), 6)
    return volValue
     
def CalculateDValue(volValue):
    dValue = round((volValue-gVolMin)*(2**20-1)/(gVolMax-gVolMin))
    return dValue
     
def SetChannelNum(channelNum, initialized):
    # set the data length to 4 
    gUDPSocketClient.setBufSize(4 + 16);
    cmdData  =  struct.pack('2B', 0, 0)  + struct.pack('B', initialized)  + struct.pack('B', channelNum) 
    Sendcommand(0x5a09,0x0000,0x5a09,0x0004,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
    data = gUDPSocketClient.receiveData() 
    # Do nothing
    # set back the data length to 8
    gUDPSocketClient.setBufSize(8+ 16)
    if (data != None):
        return True
    else:
        return False
    
def SetNewIP(IP):
    # set the data length to 4 
    global gUDPSocketClient
    gUDPSocketClient.setBufSize(4 + 16);
    # Convert IP str to int32
    packedIP = socket.inet_aton(IP)
    ipAddr = struct.unpack("L", packedIP)[0] # !	network (= big-endian)
    cmdData  =  struct.pack('L', ipAddr) 
    Sendcommand(0xd0e1,0x0000,0xd0e1,0x0004,0x0000,0x0000,0x00,0x00,0x0000, cmdData)
    # set back the data length to 8
    gUDPSocketClient.setBufSize(8+16)
    gUDPSocketClient.setIP(IP)

def SetDefaultIP(IP):
    gUDPSocketClient.setIP(IP)

def SetVolMax(volMax):
    global gVolMax
    gVolMax = volMax
    
def SetVolMin(volMin):
    global gVolMin
    gVolMin = gVolMin

gUDPSocketClient = UDPSocketClient("192.168.1.6",  6000)
