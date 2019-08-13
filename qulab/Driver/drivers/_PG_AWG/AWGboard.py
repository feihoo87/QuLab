#   FileName:AWGboard.py
#   Author:
#   E-mail:
#   All right reserved.
#   Modified: 2018.2.18
#   Description:The class of AWG
import os
import socket

import numpy as np

from . import AWGBoardDefines
import struct
from itertools import repeat

awg_para = "000423 : 1.030,1.025,1.018,1.010 : 79, 467, 154, 327"

class RAWBoard(object):
    """
        AWG 板对象

        实现与AWG硬件的连接，提供基础访问接口

        4个基础函数::

        - ``init`` 完成AWG板对象的初始化
        - ``connect`` 完成AWG板对象的连接，在连接成功后会给出AWG板对象的版本标识
        - ``disconnect`` 断开与AWG板的连接
        - ``receive_data`` 完成AWG发送的网络数据的接收
        - ``send_data`` 完成向AWG发送网络数据

        5个基础命令::

        - ``Write_Reg`` 写寄存器，完成AWG对象各模块的参数配置写入
        - ``Read_Reg`` 读寄存器，完成AWG对象各模块的参数配置读出
        - ``Read_RAM`` 读存储区，完成AWG各通道数据存储区的读出
        - ``Write_RAM`` 写存储区，完成AWG各通道数据存储区的写入
        - ``Run_Command`` 运行命令，完成AWG各通道的输出控制

        1个基础状态读取::

        - ``Read_Status_Block`` 读取AWG状态包命令
        """

    def __init__(self):
        self.board_def = AWGBoardDefines.AWGBoardDefines()
        self.port = 80
        self.dev_id = 'AWG01'
        self.dev_ip = '0.0.0.0'
        # Create a TCP/IP socket
        self.sockfd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sockfd.settimeout(5.0)
        self.soft_version = None

    def connect(self, host, dev_id=None):
        """
        :param dev_id: 可选的设备标识，如果没有给，会以IP的后两个数做设备标识
        :param host: AWG 板的IP地址
        :return:
        :notes::

            连接AWG板，连接成功，读取板上的版本标识
            连接失败，返回错误，并打印错误消息，关闭socket
        """
        self.dev_ip = host
        if dev_id:
            self.dev_id = dev_id
        else:
            s = host.split('.')[-2:]
            self.dev_id = f'AWG_{s[0]}_{s[1]}'
        print(f'AWG IP: {self.dev_ip}, ID: {self.dev_id}')
        try:
            self.sockfd.connect((host, self.port))
            print('连接成功')
            rcv_data = self.Read_RAM(0x80000000, 1024)
            self.soft_version = [int(rcv_data[718]), int(rcv_data[717]), int(rcv_data[716])]
            return 1
        except socket.error as msg:
            self.sockfd.close()
            self.sockfd = None
            print(f'ERROR:{msg}')
        if self.sockfd is None:
            print(f'ERROR:{host}:Socket打开失败')
            return -1

    def disconnect(self):
        """
        :return: None
        :notes::

            断开当前AWG对象的连接
        """
        if self.sockfd is not None:
            print('Closing socket')
            self.sockfd.close()

    def Write_Reg(self, bank, addr, data):
        """
        :param bank: 寄存器对象所属的BANK（设备或模块），4字节，只有低3字节有效
        :param addr: 偏移地址，4字节
        :param data: 待写入数据，4字节
        :return: 4字节，写入是否成功，此处的成功是指TCP/IP协议的成功，也可以等效为数据写入成功

        :notes::

            这条命令下，AWG对象返回8字节数据，4字节表示状态，4字节表示数据

        """
        cmd = self.board_def.CMD_WRITE_REG

        # I need to pack bank into 4 bytes and then only use the 3
        packed_bank = struct.pack("l", bank)
        unpacked_bank = struct.unpack('4b', packed_bank)
        packet = struct.pack("4bLL", cmd, unpacked_bank[0], unpacked_bank[1], unpacked_bank[2], addr, data)

        # Next I need to send the command
        try:
            self.send_data(packet)
        except socket.timeout:
            print("Timeout raised and caught")
        # next read from the socket
        stat = 0
        try:
            stat, data = self.receive_data()
        except socket.timeout:
            print("Timeout raised and caught")
        if stat != 0x0:
            print('Issue with Write Command stat: {}'.format(stat))
            return self.board_def.STAT_ERROR

        return self.board_def.STAT_SUCCESS

    def Read_Reg(self, bank, addr, data=0):
        """

        :param bank: 寄存器对象所属的BANK（设备或模块），4字节，只有低3字节有效
        :param addr: 偏移地址，4字节
        :param data: 待写入数据，4字节
        :return: 4字节，读取是否成功，如果成功，返回读取的数据，否则，返回错误状态

        """

        cmd = self.board_def.CMD_READ_REG

        # I need to pack bank into 4 bytes and then only use the 3
        packed_bank = struct.pack("l", bank)
        unpacked_bank = struct.unpack('4b', packed_bank)

        packet = struct.pack("4bLi", cmd, unpacked_bank[0], unpacked_bank[1], unpacked_bank[2], addr, data)
        # Next I need to send the command
        try:
            self.send_data(packet)
        except socket.timeout:
            print("Timeout raised and caught")
        # next read from the socket
        recv_stat = 0
        recv_data = 0
        try:
            recv_stat, recv_data = self.receive_data()
        except socket.timeout:
            print("Timeout raised and caught")

        if recv_stat != 0x0:
            print('Issue with Reading Register stat={}!!!'.format(recv_stat))
            return self.board_def.STAT_ERROR
        return recv_data

    def Read_RAM(self, addr, length):
        """

        :param addr: 读取存储区的起始地址
        :param length: 读取存储区的数据长度
        :return: 读取成功的数据或读取失败的错误状态

        :notes::

        """

        cmd = self.board_def.CMD_READ_MEM
        pad = 0xFAFAFA

        # I need to pack bank into 4 bytes and then only use the 3
        packed_pad = struct.pack("l", pad)
        unpacked_pad = struct.unpack('4b', packed_pad)

        packet = struct.pack("4bLL", cmd, unpacked_pad[0], unpacked_pad[1], unpacked_pad[2], addr, length)
        # Next I need to send the command
        self.send_data(packet)
        # next read from the socket
        recv_stat, recv_data = self.receive_data()
        if recv_stat != 0x0:
            print('Issue with Reading RAM stat: {}'.format(recv_stat))
            return self.board_def.STAT_ERROR
        ram_data = self.receive_RAM(int(length))
        return ram_data

    def Write_RAM(self, start_addr, data, length):
        """

        :param start_addr: 写入存储区的起始地址
        :param data: 写入存储区的数据,数据是byts类型的list
        :param length: 写入存储区的数据长度
        :return: 写入成功或失败的错误状态
        """

        cmd = self.board_def.CMD_WRITE_MEM
        pad = 0xFFFFFF
        # I need to pack bank into 4 bytes and then only use the 3
        packed_pad = struct.pack("L", pad)
        unpacked_pad = struct.unpack('4b', packed_pad)
        packet = struct.pack("4bLL", cmd, unpacked_pad[0], unpacked_pad[1], unpacked_pad[2], start_addr, length)
        # Next I need to send the command
        self.send_data(packet)
        # next read from the socket
        recv_stat, recv_data = self.receive_data()
        if recv_stat != 0x0:
            print('Ram Write cmd Error stat={}!!!'.format(recv_stat))
            return self.board_def.STAT_ERROR
        # method 1
        # format = str(len(wave))+'H'
        # format = "{0}d".format(len(wave))
        # format = "{0:d}H".format(len(data))
        # packet = struct.pack(format, *wave)
        packet = data
        self.send_data(packet)
        # next read from the socket to ensure no errors occur
        recv_stat, recv_data = self.receive_data()
        if recv_stat != 0x0:
            print('Ram Write Error stat={}!!!'.format(recv_stat))
            return self.board_def.STAT_ERROR

    def Run_Command(self, ctrl, data0, data1):
        """
        :param ctrl:  波形控制模块命令标识
        :param data0: 任意波形控制模块数据0，4字节
        :param data1: 任意波形控制模块数据1，4字节
        :return: 命令发送状态
        """
        # print(ctrl, data0, data1)
        cmd = self.board_def.CMD_CTRL_CMD
        packed_ctrl = struct.pack("l", ctrl)
        unpacked_ctrl = struct.unpack('4b', packed_ctrl)
        packet = struct.pack("4bLL", cmd, unpacked_ctrl[0], unpacked_ctrl[1], unpacked_ctrl[2], data0, data1)
        #    print ('this is my cmd packet: {}'.format(repr(packet)))
        self.send_data(packet)
        stat, data = self.receive_data()
        if stat != 0x0:
            print('Dump RAM Error stat={}!'.format(stat))
        return data

    def send_data(self, data):
        """
        :param data:  待发送数据的字节流
        :return: 命令发送状态
        """
        totalsent = 0
        while totalsent < len(data):
            sent = self.sockfd.send(data)
            if sent == 0:
                raise RuntimeError("Socket connection broken")
            totalsent = totalsent + sent

    def receive_data(self):
        """
        :return: 8字节数据，网络接口接收到的数据，仅限5条基础指令的响应数据，8字节长
        :notes::
            从网络接口接收数据
        """
        chunks = []
        bytes_recd = 0
        while bytes_recd < 8:
            # I'm reading my data in byte chunks
            chunk = self.sockfd.recv(min(8 - bytes_recd, 4))
            if chunk == '':
                raise RuntimeError("Socket connection broken")
            chunks.append(chunk)
            bytes_recd = bytes_recd + len(chunk)
        stat_tuple = struct.unpack('L', chunks[0])
        data_tuple = struct.unpack('L', chunks[1])
        stat = stat_tuple[0]
        data = data_tuple[0]
        return stat, data

    def receive_RAM(self, length):
        """
        :param length: 待读取的字节数
        :return: length字节数据，网络接口接收到的数据，仅限读取RAM和status包使用
        :notes::

            从网络接口接收数据，长度以字节为单位
            该命令配合``Read_RAM``或``Read_Status_RAM``指令实现大批量数据的读取
        """
        ram_data = b''
        bytes_recd = 0
        self.sockfd.settimeout(5)
        while bytes_recd < length:
            # I'm reading my data in byte chunks
            chunk = self.sockfd.recv(min(length - bytes_recd, 1024))
            ram_data += chunk
            if chunk == '':
                raise RuntimeError("Socket connection broken")
            bytes_recd = bytes_recd + len(chunk)
        return ram_data


class AWGBoard(RAWBoard):
    def __init__(self):
        super().__init__()
        # Initialize core AWG parameters
        self.zeros = list(repeat(0, 1024))
        self.channel_count = 4
        self.frequency = 2e9
        self.isTrigSource = 0
        self.awgTrigDelayOffset = 0
        # 电压预留系数， 0.1倍的预留空间，防止用户设置过大的偏置时，波形输出出现截止的情况
        self.coe = [1.1] * 4
        # 放大器增益系数，用于多通道之间的一致性输出校准
        self.channel_gain = [1] * self.channel_count
        # 放大器增益系数，用于多通道之间的一致性输出校准
        self.diffampgain = [1] * self.channel_count
        # 该参数是出厂时的校准值，使AWG在32768码值时整体AWG输出电压为0V（DAC输出为满伏电压的一半）
        self._calibrated_offset = [0] * self.channel_count
        # 该参数是用户设置的偏置电压，该值使AWG输出为用户指定的电压值
        self.offset_volt = [0] * self.channel_count
        # 默认0电平码值
        self.defaultcode = [32768] * self.channel_count
        # 每个通道对应的指令集执行的次数
        self.loopcnt = [60000] * self.channel_count
        # 每个通道是否在上一条指令执行后保持输出，默认不保持
        self.holdoutput = [0] * self.channel_count
        # 电压范围是负载以50欧匹配时看到的最大电压值
        self.voltrange = [1.0] * self.channel_count
        # self.fullscalecode = [1005] * self.channel_count
        # 命令集
        self.commands = [None] * self.channel_count
        # 波形集
        self.waves = [None] * self.channel_count

    # 以下是常用AWG方法
    def setAWG_ID(self, dev_id):
        """
        设置AWG的ID标识
        :return:  None
        """
        self.dev_id = dev_id
    # 以下是常用AWG方法
    def set_channel_gain(self, ch, gain=1.0):
        """
        设置AWG通道的增益
        :param ch: AWG 通道 [1,2,3,4]
        :param gain:增益系数，取值要小于等于1
        :return:  None
        """
        assert gain <= 1.0
        self.channel_gain[ch-1] = gain

    def _commit_para(self, ch):
        """
        :param self:
        :param ch: AWG 通道 [1,2,3,4]
        :return:  None，网络通信失败表示命令设置失败
        """

        self._channel_check(ch)
        # reg_low = self.holdoutput[ch - 1]
        # reg_high = (self.loopcnt[ch - 1] << 16) | self.defaultcode[ch - 1]
        # addr = (20 + ch - 1) << 2
        # self.Run_Command(self.board_def.CTRL_NEW_AWG, addr, reg_low)
        # addr = addr + 4
        # self.Run_Command(self.board_def.CTRL_NEW_AWG, addr, reg_high)
        # 老版本
        self.Run_Command(self.board_def.CTRL_SET_LOOP, (self.loopcnt[0] << 16) | self.loopcnt[1],
                         (self.loopcnt[2] << 16) | self.loopcnt[3])
        self.Run_Command(self.board_def.CTRL_DAC_DEFAULT, ch - 1, self.defaultcode[ch - 1])
        self.Run_Command(self.board_def.CTRL_SYNC_CTRL, 19, self.isTrigSource << 16)

    def SetLoop(self, ch, loopcnt):
        """
        :param self: AWG对象
        :param loopcnt: 通道ch波形输出循环次数，两字节
        :param ch: AWG 通道值（1，2，3，4）
        :return: None，网络通信失败表示命令设置失败
        """

        self._channel_check(ch)
        assert loopcnt <= 65535
        self.loopcnt[ch - 1] = loopcnt
        self._commit_para(ch)

    def Start(self, ch):
        """
        :param self: AWG对象
        :param ch: 通道输出使能[1,2,3,4]
        :return: None，网络通信失败表示命令设置失败
        :notes::
        """
        # addr = 0x34 << 2
        # self.Run_Command(self.board_def.CTRL_NEW_AWG, addr, flag << 4)
        # 老版本
        assert ch in [1,2,3,4]
        _channel = 1 << (ch -1 )
        self.Run_Command(self.board_def.CTRL_START_PLAY, _channel, 0)

    def Stop(self, ch):
        """
        :param self: AWG对象
        :param ch: 通道输出禁止[1,2,3,4]
        :return: None，网络通信失败表示命令设置失败
        :notes::
        """
        # addr = 0x34 << 2
        # self.Run_Command(self.board_def.CTRL_NEW_AWG, addr, flag << 4)
        # 老版本
        assert ch in [1,2,3,4]
        _channel = 1 << (ch -1 )
        # assert flag > 0
        self.Run_Command(self.board_def.CTRL_START_PLAY, _channel << 4, 0)

    # def SelectReadBack(self, ch):
    #     """
    #     :param self: AWG对象
    #     :param ch: (1,2,3,4) 读回通道选择
    #     :return: None，网络通信失败表示命令设置失败
    #     :notes::
    #
    #     """
    #     addr = 0x34 << 2
    #     self.Run_Command(self.board_def.CTRL_NEW_AWG, addr, 1 << (ch + 7))

    # # SPI设备寄存器写入
    # def SPI_Writr(self, spi_device_id, addr, data):
    #     """
    #     :param self: AWG对象
    #     :param spi_device_id: SPI 设备标识
    #     :param addr: SPI设备偏移地址
    #     :param data: 待写入数据
    #     :return:
    #     """
    #     self.Write_Reg(self.board_def.BANK_SPI, addr, data)
    #
    # # SPI设备寄存器读出
    # def SPI_Read(self, spi_device_id, addr):
    #     """
    #     :param self: AWG对象
    #     :param spi_device_id: SPI 设备标识
    #     :param addr: SPI设备偏移地址
    #     :return: 读出的寄存器数据
    #     """
    #     # TODO: spi_device_id合法性判断
    #     # if spi_device_id not in self.board_def.
    #     return self.Read_Reg(self.board_def.BANK_SPI, addr)

    # AWG芯片设置指令
    # id_page_map = [[1, 1], [1, 2], [2, 1], [2, 2]]

    # def EnableDIGGain(self, channel):
    #     """
    #     :param self: AWG对象
    #     :param channel: AWG 通道(1,2,3,4)
    #     :return:
    #     """
    #     spi_device_id, page = id_page_map[channel-1]
    #     SPI_Writr(self, spi_device_id, 0x008, page)  # 选中DAC通道
    #     SPI_Writr(self, spi_device_id, 0x111, 1)  # 使能DAC增益

    # def SetDIGGain(self, channel, data):
    #     """
    #     :param self: AWG对象
    #     :param channel: AWG 通道 [1,2,3,4]
    #     :param data: 增益值，该值是12位二进制补码形式的增益数据
    #
    #     :notes::
    #
    #         数字增益计算公式
    #         0 ≤ Gain ≤ 4095/2048
    #         −∞ dB ≤ dBGain ≤ 6.018 dB
    #         Gain = GainCode × (1/2048)
    #         dBGain = 20 × log10(Gain)
    #         GainCode = 2048 × Gain = 2048 × 10dBGain/20
    #     :return:
    #     """
    #     # spi_device_id, page = id_page_map[channel-1]
    #     # SPI_Writr(self, spi_device_id, 0x008, page)  # 选中DAC通道
    #     # SPI_Writr(self, spi_device_id, 0x13C, data & 0xFF)  # 写入增益值低字节
    #     # SPI_Writr(self, spi_device_id, 0x13D, (data >> 8) & 0x0F)  # 写入增益值高字节

    @staticmethod
    def _channel_check(ch):
        """
        :param ch: channel to be checked
        :return:
        """
        assert ch in [1, 2, 3, 4]

    def _SetDACMaxVolt(self, channel, volt):
        """
        :param channel: AWG 通道（1，2，3，4）
        :param volt: 最大电压值
        :return:
        """
        assert volt <= 1.351
        assert volt >= 0.696
        cur = volt / 0.05
        code = (cur - 20.48) * 1024 / 13.1
        code = int(code) & 0x3FF
        self._SetDACFullScale(channel, code)

    def _SetDACFullScale(self, channel, data):
        """
        :param self: AWG对象
        :param channel: AWG 通道 [1,2,3,4]
        :param data: 增益值，该值是12位二进制补码形式的增益数据
        :return:
        :notes::
            满电流值计算公式：
            IOUTFS = 20.48 + (DACFSC_x × 13.1 mA)/2^(10 − 1)
        """
        self._channel_check(channel)
        # id_addr_map = [[1,0x40], [1,0x44], [2, 40], [2, 44]]
        # spi_device_id, addr = id_addr_map[channel-1]
        # SPI_Writr(self, spi_device_id, addr, data & 0xFF)  # 写入满电流值低字节
        # SPI_Writr(self, spi_device_id, addr+1, (data >> 8) & 0x03)  # 写入满电流值高字节

        # 老版本
        map_ch = [2, 3, 0, 1]
        ch = map_ch[channel - 1]
        self.Write_Reg(7, ch, data)

    # 状态包地址设置
    # def SetBoardcast(self, is_boardcast, period=1, dest_ip=None):
    #     """
    #     :param self: AWG对象
    #     :param is_boardcast: 0表示禁止定时输出状态包，1表示使能状态包
    #     :param dest_ip: ip地址字符串, 类似："192.168.1.10"
    #     :return: None，网络通信失败表示命令设置失败
    #     """
    #     # data = dest_ip.split('.')
    #     # self.Write_reg(self.board_def.CTRL_MONITOR, is_boardcast, \
    #     data[3] << 24 | data[2] << 16 | data[1] << 8 | data[0])
    #     # 老版本
    #     self.Run_Command(self.board_def.CTRL_MONITOR, is_boardcast, period)

    def SetOutputHold(self, channel, is_hold):
        """
        :param self: AWG对象
        :param channel: 通道值（1，2，3，4）
        :param is_hold: 对应通道的输出是否需要保持, 1,保持，0，不保持
        :return: None，网络通信失败表示命令设置失败

        :notes::

            保持的时候波形输出会保持为最后的8个采样点
            的值不断的重复输出（此处要注意这个特性）
            该特性可以实现很少的码值输出很长的台阶波形

            在不保持时，波形输出完成后会回到设定的默认电压值
        """

        self._channel_check(channel)
        self.holdoutput[channel - 1] = is_hold
        self._commit_para(channel)

    def SetOffsetVolt(self, channel, offset_volt):
        """

        设置某个通道的偏置电压，该功能对当前通道的波形做偏执变换，可用于混频器的泄漏校准等功能
        由于是通过DA码值来实现的，因此会消耗DA的有效码值范围

        :param self: AWG对象
        :param channel: 通道值（1，2，3，4）
        :param offset_volt: 对应的偏置电压值
        :return: None，网络通信失败表示命令设置失败
        """
        # code = code + self.offsetCorr[channel - 1]
        # code = 65535 if code > 65535 else code  # 范围限制
        # code = 0 if code < 0 else code  # 范围限制
        # code = 65535 - code  # 由于负通道接示波器，数据反相方便观察

        self._channel_check(channel)
        assert abs(offset_volt) < 0.1  # 电压偏移不能超过 ±0.1V
        volt = offset_volt
        if abs(volt) > self.voltrange[channel - 1]:
            print(f'偏移电压设置值{volt}超过AWG范围[{-self.voltrange[channel-1]}-{self.voltrange[channel-1]}], 电压值将会设为0')
            volt = 0

        code = int(volt * 65535 / self.coe[channel - 1] / (2 * self.voltrange[channel - 1]))
        self._SetDacOffset(channel, code)
        self.offset_volt[channel - 1] = offset_volt

    def _SetCalibratedOffsetCode(self, channel, offset_code):
        """

        该函数设置的偏置值用于校准仪器在默认连接时的0电平码值
        :param channel: AWG通道[1，2，3，4]
        :param offset_code: 偏置码值
        :return:
        """
        self._channel_check(channel)
        self._calibrated_offset[channel - 1] = offset_code

    def _SetDacOffset(self, channel, offset_code):
        """

        :param self: AWG对象
        :param channel: 通道值（1，2，3，4）
        :param offset_code: 对应的DA通道的offset值，精度到1个LSB
        :return: None，网络通信失败表示命令设置失败
        """

        self._channel_check(channel)
        # self.user_setted_offset[channel - 1] = offset_code

        ch_map = [3, 4, 1, 2]
        ch = ch_map[channel - 1]
        dac_sel = (((ch - 1) >> 1) + 1) << 24
        page = ((ch - 1) & 0x01) + 1
        temp1 = (offset_code + self._calibrated_offset[channel - 1] >> 0) & 0xFF
        temp2 = (offset_code + self._calibrated_offset[channel - 1] >> 8) & 0xFF
        self.Run_Command(self.board_def.CTRL_DAC_WRITE, data1=(dac_sel | 0x008), data0=page)
        self.Run_Command(self.board_def.CTRL_DAC_WRITE, data1=(dac_sel | 0x135), data0=1)  # 使能offset
        self.Run_Command(self.board_def.CTRL_DAC_WRITE, data1=(dac_sel | 0x136), data0=temp1)  # LSB [7:0]
        self.Run_Command(self.board_def.CTRL_DAC_WRITE, data1=(dac_sel | 0x137), data0=temp2)  # LSB [15:8]
        self.Run_Command(self.board_def.CTRL_DAC_WRITE, data1=(dac_sel | 0x13A), data0=0)  # SIXTEEN [4:0]

    # def SetDefaultCode(self, channel, code):
    #     """
    #     :param self: AWG对象
    #     :param channel: 通道值（1，2，3，4）
    #     :param code: 对应的DA码值
    #     :return: None，网络通信失败表示命令设置失败
    #     """
    #     # code = code + self.offsetCorr[channel - 1]
    #     # code = 65535 if code > 65535 else code  # 范围限制
    #     # code = 0 if code < 0 else code  # 范围限制
    #     # code = 65535 - code  # 由于负通道接示波器，数据反相方便观察
    #
    #     self._channel_check(channel)
    #     self.defaultcode[channel - 1] = code
    #     self._commit_para(channel)

    # def _SetDefaultvolt(self, channel, volt):
    #     """
    #
    #     该函数目前没有什么用了
    #     :param self: AWG对象
    #     :param channel: 通道值（1，2，3，4）
    #     :param volt: 对应电压值，应该要介于DA支持的最大值与最小值之间
    #     :return:  None，网络通信失败表示命令设置失败
    #     """
    #
    #     self._channel_check(channel)
    #     if volt > self.voltrange[channel - 1][1] or volt < self.voltrange[channel - 1][0]:
    #         print(f'电压设置值{volt}超过AWG范围[{self.voltrange[channel-1][0]}-{self.voltrange[channel-1][1]}], 电压值将会设为0')
    #         volt = 0
    #     code = int(volt * 65535 / (self.voltrange[channel - 1][1] - self.voltrange[channel - 1][0]))
    #     self.SetDefaultCode(channel, code)

    def _AWGChannelSelect(self, ch, cmd_or_wave):
        """

        :param self: AWG对象
        :param ch: 通道值（1，2，3，4）
        :param cmd_or_wave: 命令通道（0）或波形数据通道（1）
        :return: None，网络通信失败表示命令设置失败
        """

        self._channel_check(ch)
        addr = 0x30 << 2
        self.Run_Command(self.board_def.CTRL_NEW_AWG, addr, 1 << (ch - 1 + cmd_or_wave * 4))

    @staticmethod
    def _format_data(data):
        """
        :param data: 准备格式化的数据
        :return: 格式化后的数据
        :notes::
            输入的数据是无符号short类型数据，转换成网络接口接受的字节流
        """
        fmt = "{0:d}H".format(len(data))
        packet = struct.pack(fmt, *data)
        return packet

    def _WriteWaveCommands(self, ch, commands):
        """
        :param self: AWG对象
        :param ch: 通道值（1，2，3，4）
        :param commands: 波形输出控制指令数据
        :return: None，网络通信失败表示命令设置失败
        """
        self._channel_check(ch)
        # startaddr = 0
        # self._AWGChannelSelect(ch, 1)  # 1表示命令
        # 老版本
        startaddr = (ch * 2 - 1) << 18  # 序列的内存起始地址，单位是字节。
        pad_cnt = 32 - len(commands) & 0x1F
        temp_cmd = commands + [0] * pad_cnt
        packet = self._format_data(temp_cmd)
        self.Write_RAM(startaddr, packet, len(packet))

    def _WriteWaveData(self, ch, wave):
        """
        :param self: AWG对象
        :param ch: 通道值（1，2，3，4）
        :param wave: 波形输出数据
        :return: None，网络通信失败表示命令设置失败
        """

        self._channel_check(ch)
        # wave = list((np.asarray(wave) + self.defaultcode[ch - 1]-32767).astype(np.int32))
        assert max(wave) < 65535  # 码值异常，大于上限
        assert min(wave) > 0  # 码值异常，小于下限
        # startaddr = 0
        # self._AWGChannelSelect(ch, 0)  # 0表示波形数据

        # 老版本
        startaddr = (ch - 1) << 19  # 波形数据的内存起始地址，单位是字节。
        pad_cnt = 32 - len(wave) & 0x1F
        temp_wave = wave + [self.defaultcode[ch - 1]] * pad_cnt
        packet = self._format_data(temp_wave)
        self.Write_RAM(startaddr, packet, len(packet))

    @staticmethod
    def _get_volt(value):
        """
        返回满电流码值对应的电压值
        :param value: 满电流码值
        :return: 电压值
        """
        sign = value >> 9
        code = value & 0x1FF
        # print(code, sign)
        volts = (20.48 + ((code - (sign << 9)) * 13.1) / 1024) * 0.05
        return volts

    @staticmethod
    def gen_wave_unit(wave_data, wave_type='延时', start_time=0):
        """
        生成描述一个波形的波形字典单元
        返回字典类型的元组
        """
        return {'wave_data': wave_data, 'wave_type': wave_type, 'start_time': start_time}

    def wave_compile(self, ch, waves_list, is_continue=False):
        """
        编译并合成多个波形，每个波形的类型，起始时间，波形数据均由用户提供

        :param is_continue: 是否要生成连续输出的波形，该值为真时，最终合成的波形是周期性连续不断输出，不需要等待触发信号
        :param ch: 编译的波形对应的AWG通道
        :param waves_list: 要合成的波形序列序列中每个单元应该包含:

            wave_list:  波形数据列表

            type_list: 每个要合成的波形的类型

            start_time_list: 波形输出起始时间，以第一条指令的对应触发为0时刻，所有波形的输出时间均相对最近的触发指令0时刻计算，
            所有的触发指令都会使计时清零，即触发指令充当了重新同步的功能

        :return: 波形类得到合成后的波形数据，相应的控制命令集

        :notes::

            这类波形的第一条一般都是触发类型的，配上其他的波形类型
            输出可以实现指定时间输出指定波形的功能，所有输出的参考
            时间是相对于最近一条触发指令的触发沿的

            每一条触发类型的波形都可以重新实现与输入触发信号的同步对齐
        """
        # TODO:首先对输入的波形序列做预处理，两段波形输出间隔过小(小于16ns)的，可以合并成一条波形（暂时没做, 只做了长度判断）

        # 修整后，每一条指令会完整的输出至少一段波形

        self._channel_check(ch)

        wave_list = []
        type_list = []
        start_time_list = []

        volt_factor = self.coe[ch-1]  # self.voltrange[ch - 1][1] - self.voltrange[ch - 1][0]
        for item in waves_list:
            # 电压到码值的转换，为了给偏执留余量，要求最大输出电压比给用户的电压多10%，对于vpp为2V的AWG，其最大电压输出其实能到2.2V
            a1 = np.asarray(item['wave_data'])
            a1 = a1.astype(np.float) * self.channel_gain[ch -1]
            # print(a1)
            a1 = a1 / volt_factor
            a1 = (a1 + 1) * 32767.5
            trans_wave = list(a1.astype(np.uint16))
            wave_list.append(trans_wave)
            type_list.append(item['wave_type'])
            start_time_list.append(item['start_time'])

        cur_sample_point = 0
        wave = []
        command = []
        for idx, wave_type in enumerate(type_list):
            if wave_type == '触发':
                """触发类型的指令需要配一个延时参数，表示触发信号到达后，延时多少时间输出，延时精度4ns
                触发指令可以看做重新同步指令，那么，一串的波形就可以通过触发指令分割成多个序列来处理
                所以，触发指令一定是当做第一条指令来处理，他的起始时刻重新归零计算，但是地址要相对已有波形最后一个点

                触发波形对应的命令有3个参数：延时计数，波形起始地址，输出长度
                """
                cmd_id = 0x4000
                cur_sample_point = 0
            elif wave_type == '跳转':
                cmd_id = 0x0000
                pass
            else:
                cmd_id = 0x2000

            # 计算起始时间对应的采样点
            # print('波形长度',len(wave_list[idx]))
            assert len(wave_list[idx]) >= 32
            sample_cnt = round(start_time_list[idx] * self.frequency)
            # 计算与上一个结束时间的采样点间隔，如果时间重叠
            delta_cnt = (sample_cnt - cur_sample_point)
            assert delta_cnt >= 0, '时间重叠'
            # 计算延时计数器的值
            delay_cnt = delta_cnt >> 3
            # 如果起始时间与计数器不对齐，通过波形点前面补齐
            pad_cnt = delta_cnt & 0x07
            temp_wave = [self.defaultcode[ch - 1]] * pad_cnt
            temp_wave = temp_wave + wave_list[idx]
            # 如果补齐后的结束时间与时钟周期不对齐，通过波形点后面补齐
            pad_cnt = (8 - len(temp_wave) & 0x07) & 0x07
            temp_wave = temp_wave + [self.defaultcode[ch - 1]] * pad_cnt

            # 生成起始地址，波形长度
            start_addr = len(wave) >> 3
            length = (len(temp_wave) >> 3)
            # 生成对应的命令
            # print(start_addr, length)
            assert start_addr + length <= (100000 >> 3), '波形范围越界'
            assert delay_cnt <= 65535, '延时计数超过最大值'
            temp_cmd = [start_addr, length, delay_cnt, cmd_id]

            # 拼接命令集与波形集
            command = command + temp_cmd
            wave = wave + temp_wave
            cur_sample_point += (delay_cnt << 3) + len(temp_wave)

        # 最后一条命令要带停止标识，标识是最后一条命令
        self.waves[ch - 1] = list(wave)

        if len(command) == 4 and not is_continue:
            self.commands[ch - 1] = command * 4096
        else:
            command[-1] |= 0x8000
            self.commands[ch - 1] = list(command)
        if is_continue:
            self.commands[ch - 1] = [0, len(wave) >> 3, 0, 0] * 4096

        # 将编译的波形上传到AWG
        self._upload_data(ch)

    def display_AWG(self):
        """
        :param self: AWG对象
        :return: 打印AWG信息
        """
        print(f'AWG标识：{self.dev_id}，地址：{self.dev_ip}')
        print(f'AWG采样率(GSPS)：{self.frequency/1e9}')
        print(f'AWG分辨率：16bit')
        print(f'AWG通道数：{self.channel_count}')
        for ch in range(self.channel_count):
            print(f'AWG通道{ch+1}电压范围：{-self.voltrange[ch]}-{self.voltrange[ch]}V')
        s = [str(i) for i in self.offset_volt]
        print('各通道偏置电压值（V）:' + ','.join(s))

    def _load_init_para(self):
        """
        加载初始化参数文件

        :param self:
        :return:
        """
        # with open('awg_paras.txt', r) as f:
        # para_list = []
        # with open(r'awg_para.txt', 'r') as f:
        #     lines = f.readlines()

            # for line in lines:
        line = awg_para
        line = line.strip('\n').split(':')
        if line[0].strip() == self.dev_id or line[0].strip() == '000423':
                    self._calibrated_offset = [int(i.strip()) for i in line[2].split(',')]
                    self.diffampgain = [float(i.strip()) for i in line[1].split(',')]
                    print(self._calibrated_offset, self.diffampgain)
                    print('初始化参数加载正常')
                    return
        # print(f'没有找到设备ID：{self.dev_id}对应的初始化参数，请检查设备ID名称或提供校准参数')

    def InitBoard(self):
        """
        初始化AWG，该命令在AWG状态异常时使用,使AWG回到初始状态，并停止输出

        :param self:
        :return:
        """
        self._load_init_para()
        self.Stop(1)
        self.Stop(2)
        self.Stop(3)
        self.Stop(4)
        self.Run_Command(self.board_def.CTRL_INIT, 0, 0)
        for ch in range(self.channel_count):
            self._commit_para(ch + 1)
            self._SetDACMaxVolt(ch + 1, self.voltrange[ch] * self.diffampgain[ch])
            self.SetOffsetVolt(ch + 1, 0)

    def _upload_data(self, ch):
        """
        加载某一通道的波形数据与序列数据
        加载会导致相应的通道停止输出
        :param ch: AWG通道（1，2，3，4）
        :return:
        """
        self._channel_check(ch)
        self.Stop(ch)
        self._WriteWaveData(ch, self.waves[ch - 1])
        self._WriteWaveCommands(ch, self.commands[ch - 1])
        # self.Start(1 << (ch - 1))
        # 还是由用户显示的启动AWG
