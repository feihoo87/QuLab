#   FileName:AWGboard.py
#   Author:
#   E-mail:
#   All right reserved.
#   Modified: 2019.2.18
#   Description:The class of AWG
import os
import socket
import time

import numpy as np

from . import AWGBoardDefines
#import AWGBoardDefines
import struct
from itertools import repeat

awg_para = {
'000423' : [[1.030,1.025,1.018,1.010], [79, 467, 154, 327]],
'000106' : [[1.045,1.045,1.049,1.038], [ 400, 315, 510, 435]],
'C18EFFFE1':[[1.162,1.16,1.144,1.138], [193,259,411,279]],
'C18EFFFE2':[[1.118,1.116,1.146,1.146], [46,106,14,-135]],
'C18EFFFE3':[[1.162,1.166,1.13,1.138], [493,352,396,422]],
'C18EFFFE4':[[1.316,1.252,1.264,1.25], [-337,376,-512,242]],
}


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

        4个基础命令::

        - ``Write_Reg`` 写寄存器，完成AWG对象各模块的参数配置写入
        - ``Read_Reg`` 读寄存器，完成AWG对象各模块的参数配置读出
        - ``Read_RAM`` 读存储区，完成AWG各通道数据存储区的读出
        - ``Write_RAM`` 写存储区，完成AWG各通道数据存储区的写入

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
        self.soft_version = 1.1

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
        
        try:
            self.sockfd.connect((host, self.port))
            print('连接成功')
            # 读取硬件ID
            self.dev_id = self.Read_Reg(8, 0, 0)
            print(f'AWG IP: {self.dev_ip}, ID: {self.dev_id}')
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
        :param bank: 寄存器对象所属的BANK（设备或模块），4字节
        :param addr: 偏移地址，4字节
        :param data: 待写入数据，4字节
        :return: 4字节，写入是否成功，此处的成功是指TCP/IP协议的成功，也可以等效为数据写入成功

        :notes::

            这条命令下，AWG对象返回8字节数据，4字节表示状态，4字节表示数据

        """
        cmd = self.board_def.CMD_WRITE_REG
        packet = struct.pack(">LLLL", cmd, bank, addr, data)
        try:
            self.send_data(packet)
        except socket.timeout:
            print("Timeout raised and caught")
        stat = 0
        try:
            stat, data, data2 = self.receive_data()
        except socket.timeout:
            print("Timeout raised and caught")
        if stat != 0x0:
            print('Issue with Write Command stat: {}'.format(stat))
            return self.board_def.STAT_ERROR
        return self.board_def.STAT_SUCCESS

    def Read_Reg(self, bank, addr, data=0):
        """
        :param bank: 寄存器对象所属的BANK（设备或模块），4字节
        :param addr: 偏移地址，4字节
        :param data: 待写入数据，4字节
        :return: 4字节，读取是否成功，如果成功，返回读取的数据，否则，返回错误状态

        """
        cmd = self.board_def.CMD_READ_REG
        packet = struct.pack(">LLLL", cmd, bank, addr, data)
        try:
            self.send_data(packet)
        except socket.timeout:
            print("Timeout raised and caught")
        recv_stat = 0
        recv_data = 0
        try:
            recv_stat, recv_data, recv_data2 = self.receive_data()

        except socket.timeout:
            print("Timeout raised and caught")

        if recv_stat != 0x0:
            print('Issue with Reading Register stat={}!!!'.format(recv_stat))
            return self.board_def.STAT_ERROR
        if bank == 8:
            return '{:X}'.format((recv_data2<<16)+(recv_data>>16))
        return recv_data

    def Read_RAM(self, bank, addr, length):
        """
        :param bank: 数据对象所属的BANK（设备或模块），4字节
        :param addr: 读取存储区的起始地址
        :param length: 读取存储区的数据长度
        :return: 读取成功的数据或读取失败的错误状态

        :notes::

        """
        cmd = self.board_def.CMD_READ_MEM
        packet = struct.pack(">LLLL", cmd, bank, addr, length)
        self.send_data(packet)
        # next read from the socket, read length has 20 byte head
        recv_stat, ram_data = self.receive_RAM(int(length + 20))
        if recv_stat != 0x0:
            print('Issue with Reading RAM stat: {}'.format(recv_stat))
            return self.board_def.STAT_ERROR

        return ram_data, recv_stat

    def Write_RAM(self, bank, start_addr, data, length):
        """
        :param bank: 数据对象所属的BANK（设备或模块），4字节
        :param start_addr: 写入存储区的起始地址
        :param data: 写入存储区的数据,数据是byts类型的list
        :param length: 写入存储区的数据长度
        :return: 写入成功或失败的错误状态
        """
        cmd = self.board_def.CMD_WRITE_MEM
        packet = struct.pack(">LLLL", cmd, bank, start_addr, length)
        packet = packet + data
        self.send_data(packet)
        recv_stat, recv_data, recv_data2 = self.receive_data()
        if recv_stat != 0x0:
            print('Ram Write cmd Error stat={}!!!'.format(recv_stat))
            return self.board_def.STAT_ERROR

    def send_data(self, data):
        """
        :param data:  待发送数据的字节流
        :return: 命令发送状态（已发送字节数）
        """
        totalsent = 0
        while totalsent < len(data):
            sent = self.sockfd.send(data)
            if sent == 0:
                raise RuntimeError("Socket connection broken")
            totalsent = totalsent + sent
        return totalsent

    def receive_data(self):
        """
        :return: 20字节数据，网络接口接收到的数据，仅限4条基础指令的响应数据，5个4字节，20字节长
        :notes::
            从网络接口接收数据，接收到的是发送方发送的数据加上读请求返回的寄存器数据

            +-------------+----------------------+----------------+------------+----------+
            | 写寄存器标识| 模块标识             | 寄存器偏移地址 | 写寄存器值 | 返回值   |
            +-------------+----------------------+----------------+------------+----------+
            | 0xAAAAAAAA  | 32位(见模块标识定义) | 32位           | 32位       | 0表示正常|
            +-------------+----------------------+----------------+------------+----------+
            | 读寄存器标识| 模块标识             | 寄存器偏移地址 | 写寄存器值 | 返回值   |
            +-------------+----------------------+----------------+------------+----------+
            | 0x55555555  | 32位(见模块标识定义) | 32位           | 32位       | 0表示正常|
            +-------------+----------------------+----------------+------------+----------+
            | 写RAM标识   | 模块标识             | 寄存器偏移地址 | 写寄存器值 | 返回值   |
            +-------------+----------------------+----------------+------------+----------+
            | 0x55AAAA55  | 32位(见模块标识定义) | 32位           | 32位       | 0表示正常|
            +-------------+----------------------+----------------+------------+----------+
        """
        chunks = b''
        bytes_recd = 0
        while bytes_recd < 20:
            tmp = self.sockfd.recv(min(20 - bytes_recd, 20))
            if tmp == '':
                raise RuntimeError("Socket connection broken")
            chunks += tmp
            bytes_recd = bytes_recd + len(tmp)
        stat_tuple = struct.unpack('>LLLLL', chunks)
        stat = stat_tuple[-1]
        data = stat_tuple[-2]
        data2 = stat_tuple[-3]
        return stat, data, data2

    def receive_RAM(self, length):
        """
        :param length: 待读取的字节数
        :return: length字节数据，网络接口接收到的数据，仅限读取RAM和status包使用
        :notes::
            从网络接口接收数据，长度以字节为单位
            该命令配合``Read_RAM``或``Read_Status_RAM``指令实现大批量数据的读取

            +-------------+----------------------+----------------+------------+----------+
            | 读RAM标识   | 模块标识             | 寄存器偏移地址 | 读回数据   | 返回值   |
            +-------------+----------------------+----------------+------------+----------+
            | 0xAA5555AA  | 32位(见模块标识定义) | 32位           | 最大1MB    | 0表示正常|
            +-------------+----------------------+----------------+------------+----------+


        """
        ram_data = b''
        bytes_recd = 0
        self.sockfd.settimeout(5)
        while bytes_recd < length:
            chunk = self.sockfd.recv(min(length - bytes_recd, length))
            ram_data += chunk
            if chunk == '':
                raise RuntimeError("Socket connection broken")
            bytes_recd = bytes_recd + len(chunk)

        return ram_data[:-4], ram_data[-4:-1]


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
        # DAC增益系数，用于多通道之间的一致性输出校准
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
        # 命令集
        self.commands = [None] * self.channel_count
        # 波形集
        self.waves = [None] * self.channel_count
        self.bank_dic = {'awg': [self.board_def.CHIP_AWG_1,
                                 self.board_def.CHIP_AWG_1,
                                 self.board_def.CHIP_AWG_2,
                                 self.board_def.CHIP_AWG_2],
                         'dac': [self.board_def.CHIP_9136_1,
                                 self.board_def.CHIP_9136_1,
                                 self.board_def.CHIP_9136_2,
                                 self.board_def.CHIP_9136_2]
                         }

    # 以下是常用AWG方法

    def setAWG_ID(self, dev_id):
        """
        设置AWG的ID标识
        :return:  None
        """
        self.dev_id = dev_id

    # 以下是常用AWG方法
    def set_channel_gain(self, channel, gain=1.0):
        """
        设置AWG通道的增益
        :param channel: AWG 通道 [1,2,3,4]
        :param gain:增益系数，取值要小于等于1
        :return:  None
        """
        assert gain <= 1.0
        self.channel_gain[channel - 1] = gain

    def _commit_para(self, channel):
        """
        提交AWG的配置参数
        :param self:
        :param channel: AWG 通道 [1,2,3,4]
        :return:  None，网络通信失败表示命令设置失败
        """

        self._channel_check(channel)
        bank = self.bank_dic['awg'][channel - 1]
        sub_ch = (((channel - 1) & 0x01) << 3)
        reg_low = self.holdoutput[channel - 1] | (self.defaultcode[channel - 1] << 16)
        reg_high = self.loopcnt[channel - 1]
        addr = self.board_def.REG_CNFG_REG0 + sub_ch
        self.Write_Reg(bank, addr, reg_low)
        addr = addr + 4
        self.Write_Reg(bank, addr, reg_high)

    def SetLoop(self, channel, loopcnt):
        """
        :param self: AWG对象
        :param loopcnt: 通道ch波形输出循环次数，两字节
        :param channel: AWG 通道值（1，2，3，4）
        :return: None，网络通信失败表示命令设置失败
        """

        self._channel_check(channel)
        self.loopcnt[channel - 1] = loopcnt
        self._commit_para(channel)

    def Start(self, channel):
        """
        :param self: AWG对象
        :param channel: 通道输出使能[1,2,3,4]
        :return: None，网络通信失败表示命令设置失败
        :notes::
        """

        assert channel in [1, 2, 3, 4]
        self._channel_check(channel)
        _channel = 1 << ((channel - 1) & 0x01)
        _bank = self.bank_dic['awg'][channel - 1]
        self.Write_Reg(_bank, self.board_def.REG_CTRL_REG, _channel)

    def Stop(self, channel):
        """
        :param self: AWG对象
        :param channel: 通道输出禁止[1,2,3,4]
        :return: None，网络通信失败表示命令设置失败
        :notes::
        """
        assert channel in [1, 2, 3, 4]
        self._channel_check(channel)
        _channel = 16 << ((channel - 1) & 0x01)
        _bank = self.bank_dic['awg'][channel - 1]
        self.Write_Reg(_bank, self.board_def.REG_CTRL_REG, _channel)

    @staticmethod
    def _channel_check(channel):
        """
        :param channel: channel to be checked
        :return:
        """
        assert channel in [1, 2, 3, 4]

    def _SetDACMaxVolt(self, channel, volt):
        """

        该函数用于设置芯片的最大输出电压

        :param channel: AWG 通道（1，2，3，4）
        :param volt: 最大电压值
        :return:
        :notes::
            满电流值计算公式：
            IOUTFS = 20.48 + (DACFSC_x × 13.1 mA)/2^(10 ? 1)
        """
        assert volt <= 1.351
        assert volt >= 0.696
        cur = volt / 0.05
        code = (cur - 20.48) * 1024 / 13.1
        code = int(code) & 0x3FF
        self._SetDACFullScale(channel, code)

    def _SetDACFullScale(self, channel, data):
        """

        该函数根据输入的码值写入芯片

        :param self: AWG对象
        :param channel: AWG 通道 [1,2,3,4]
        :param data: 增益值，该值是12位二进制补码形式的增益数据
        :return:

        """
        self._channel_check(channel)
        _bank = self.bank_dic['dac'][channel - 1]
        addr = 0x40 + 4 * ((channel-1)&0x01)
        self.Write_Reg(_bank, addr+1, data & 0xFF)  # 写入满电流值低字节
        self.Write_Reg(_bank, addr, (data >> 8) & 0x03)  # 写入满电流值高字节

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

        设置某个通道的偏置电压，该功能对当前通道的波形做偏置设置
        由于是通过DA码值来实现的，因此会消耗DA的有效码值范围

        :param self: AWG对象
        :param channel: 通道值（1，2，3，4）
        :param offset_volt: 对应的偏置电压值
        :return: None，网络通信失败表示命令设置失败
        """

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
        page = ((channel - 1) & 0x01) + 1
        temp1 = (offset_code + self._calibrated_offset[channel - 1] >> 0) & 0xFF
        temp2 = (offset_code + self._calibrated_offset[channel - 1] >> 8) & 0xFF

        _bank = self.bank_dic['dac'][channel - 1]
        self.Write_Reg(_bank, 0x008, page)  # 分页
        self.Write_Reg(_bank, 0x135, 1)  # 使能offset
        self.Write_Reg(_bank, 0x136, temp1)  # LSB [7:0]
        self.Write_Reg(_bank, 0x137, temp2)  # LSB [15:8]
        self.Write_Reg(_bank, 0x13A, 0)  # SIXTEEN [4:0]

    def _AWGChannelSelect(self, channel, cmd_or_wave):
        """

        :param self: AWG对象
        :param channel: 通道值（1，2，3，4）
        :param cmd_or_wave: 命令通道（0）或波形数据通道（1）
        :return: None，网络通信失败表示命令设置失败
        """

        self._channel_check(channel)
        assert cmd_or_wave in [0,1]
        _bank = self.bank_dic['awg'][channel - 1]
        pos = ((channel-1) & 0x01) + (cmd_or_wave << 2)
        self.Write_Reg(_bank, self.board_def.REG_CNFG_REG4, 1 << pos)


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

    def _WriteWaveCommands(self, channel, commands):
        """
        :param self: AWG对象
        :param channel: 通道值（1，2，3，4）
        :param commands: 波形输出控制指令数据
        :return: None，网络通信失败表示命令设置失败
        """
        self._channel_check(channel)
        self._AWGChannelSelect(channel, 0)  # 0表示命令
        startaddr = 0  # 序列的内存起始地址，单位是字节。
        packet = self._format_data(commands)
        _bank = self.bank_dic['awg'][channel - 1]
        # TODO, PCIE 时还需要修改
        offset = 0
        unit_size = 1024
        cycle_cnt = int(len(packet) / unit_size)  #
        for _ in range(cycle_cnt):
            self.Write_RAM(_bank, startaddr, packet[offset:offset + unit_size], unit_size)
            startaddr += (unit_size >> 2)
            offset += unit_size
        if len(packet) & (unit_size - 1) > 0:
            self.Write_RAM(_bank, startaddr, packet[offset:], len(packet) & (unit_size - 1))

    def _WriteWaveData(self, channel, wave):
        """
        :param self: AWG对象
        :param channel: 通道值（1，2，3，4）
        :param wave: 波形输出数据
        :return: None，网络通信失败表示命令设置失败
        """

        self._channel_check(channel)
        assert max(wave) < 65535  # 码值异常，大于上限
        assert min(wave) > 0  # 码值异常，小于下限
        self._AWGChannelSelect(channel, 1)  # 1表示波形数据
        startaddr = 0  # 波形数据的内存起始地址，单位是字节。
        pad_cnt = (2 - len(wave) & 0x01) & 0x01
        temp_wave = wave + [self.defaultcode[channel - 1]] * pad_cnt

        packet = self._format_data(temp_wave)
        _bank = self.bank_dic['awg'][channel - 1]

        # TODO, PCIE 时还需要修改
        offset = 0
        unit_size = 1024
        cycle_cnt = int(len(packet) / unit_size)  #
        for _ in range(cycle_cnt):
            self.Write_RAM(_bank, startaddr, packet[offset:offset + unit_size], unit_size)
            startaddr += (unit_size >> 2)
            offset += unit_size
        if len(packet) & (unit_size - 1) > 0:
            self.Write_RAM(_bank, startaddr, packet[offset:], len(packet) & (unit_size - 1))


    @staticmethod
    def _get_volt(value):
        """
        返回满电流码值对应的电压值
        :param value: 满电流码值
        :return: 电压值
        """
        sign = value >> 9
        code = value & 0x1FF
        volts = (20.48 + ((code - (sign << 9)) * 13.1) / 1024) * 0.05
        return volts

    @staticmethod
    def gen_wave_unit(wave_data, wave_type='延时', start_time=0):
        """
        生成描述一个波形的波形字典单元
        返回字典类型的元组
        """
        return {'wave_data': wave_data, 'wave_type': wave_type, 'start_time': start_time}

    def wave_compile(self, channel, waves_list, is_continue=False):
        """
        编译并合成多个波形，每个波形的类型，起始时间，波形数据均由用户提供

        :param is_continue: 是否要生成连续输出的波形，该值为真时，最终合成的波形是周期性连续不断输出，不需要等待触发信号
        :param channel: 编译的波形对应的AWG通道
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

        self._channel_check(channel)

        wave_list = []
        type_list = []
        start_time_list = []

        volt_factor = self.coe[channel - 1]  # self.voltrange[channel - 1][1] - self.voltrange[channel - 1][0]
        for item in waves_list:
            # 电压到码值的转换，为了给偏执留余量，要求最大输出电压比给用户的电压多10%，对于vpp为2V的AWG，其最大电压输出其实能到2.2V
            a1 = np.asarray(item['wave_data'])
            a1 = a1.astype(np.float) * self.channel_gain[channel - 1]
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
            if wave_type in ['触发','trig'] :
                """触发类型的指令需要配一个延时参数，表示触发信号到达后，延时多少时间输出，
                触发指令可以看做重新同步指令，那么，一串的波形就可以通过触发指令分割成多个序列来处理
                所以，触发指令一定是当做第一条指令来处理，他的起始时刻重新归零计算，但是地址要相对已有波形最后一个点
                触发波形对应的命令有3个参数：延时计数，波形起始地址，输出长度
                """
                cmd_id = 0x4000
                cur_sample_point = 0
            elif wave_type in ['延时','delay'] :
                cmd_id = 0x2000
            elif wave_type in ['延时','cont']:
                cmd_id = 0x0000
                is_continue = True

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
            temp_wave = [self.defaultcode[channel - 1]] * pad_cnt
            temp_wave = temp_wave + wave_list[idx]
            # 如果补齐后的结束时间与时钟周期不对齐，通过波形点后面补齐
            pad_cnt = (8 - len(temp_wave) & 0x07) & 0x07
            temp_wave = temp_wave + [self.defaultcode[channel - 1]] * pad_cnt

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
        self.waves[channel - 1] = list(wave)

        if len(command) == 4 and not is_continue:
            self.commands[channel - 1] = command * 4096
        else:
            command[-1] |= 0x8000
            self.commands[channel - 1] = list(command)
        if is_continue:
            self.commands[channel - 1] = [0, len(wave) >> 3, 0, 0] * 4096

        # 将编译的波形上传到AWG
        self._upload_data(channel)

    def display_AWG(self):
        """
        :param self: AWG对象
        :return: 打印AWG信息
        """
        print(f'AWG标识：{self.dev_id}，地址：{self.dev_ip}')
        print(f'AWG采样率(GSPS)：{self.frequency/1e9}')
        print(f'AWG分辨率：16bit')
        print(f'AWG通道数：{self.channel_count}')
        for channel in range(self.channel_count):
            print(f'AWG通道{channel+1}电压范围：{-self.voltrange[channel]}-{self.voltrange[channel]}V')
        s = [str(i) for i in self.offset_volt]
        print('各通道偏置电压值（V）:' + ','.join(s))

    def _load_init_para(self):
        """
        加载初始化参数文件

        :param self:
        :return:
        """
        self._calibrated_offset = awg_para[self.dev_id][1]
        self.diffampgain = awg_para[self.dev_id][0]
        # line = awg_para
        # line = line.strip('\n').split(':')
        # if line[0].strip() == self.dev_id or line[0].strip() == '000423':
        #     self._calibrated_offset = [int(i.strip()) for i in line[2].split(',')]
        #     self.diffampgain = [float(i.strip()) for i in line[1].split(',')]
        print(self._calibrated_offset, self.diffampgain)
        print('初始化参数加载正常')
        return

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
        self.dac_init(1)
        self.dac_init(2)
        # self.Run_Command(self.board_def.CTRL_INIT, 0, 0)
        for channel in range(self.channel_count):
            self._commit_para(channel + 1)
            self._SetDACMaxVolt(channel + 1, self.voltrange[channel] * self.diffampgain[channel])
            self.SetOffsetVolt(channel + 1, 0)

    def _upload_data(self, channel):
        """
        加载某一通道的波形数据与序列数据
        加载会导致相应的通道停止输出
        :param channel: AWG通道（1，2，3，4）
        :return:
        """
        self._channel_check(channel)
        self.Stop(channel)
        self._WriteWaveData(channel, self.waves[channel - 1])
        self._WriteWaveCommands(channel, self.commands[channel - 1])
        # self.Start(1 << (channel - 1))
        # 还是由用户显示的启动AWG

    def dac_init(self, chip):
        """

        初始化DAC配置

        :param chip: dac chip 1 or 2
        :return:

        """
        try_cnt = 5
        while try_cnt > 0:
            try_cnt -= 1
            if self.Read_Reg(chip, 0x147) & 0xFF == 0x00C0:
                break
            if try_cnt == 0:
                print(f'dac chip {chip} 初始化失败')
                break
            self.Write_Reg(chip, 0x47d, 0xff)
            self.Write_Reg(chip, 0x00a, 0xAD)

            self.Write_Reg(chip, 0x000, 0x81)
            self.Write_Reg(chip, 0x000, 0x18)

            self.Write_Reg(chip, 0x12F, 0x21)
            self.Write_Reg(chip, 0x011, 0xFF)
            self.Write_Reg(chip, 0x011, 0x00)

            self.Write_Reg(chip, 0x080, 0x00)
            self.Write_Reg(chip, 0x081, 0x00)

            self.Write_Reg(chip, 0x034, 0x00)
            self.Write_Reg(chip, 0x12d, 0x8b)
            self.Write_Reg(chip, 0x146, 0x01)
            self.Write_Reg(chip, 0x2a4, 0xff)

            self.Write_Reg(chip, 0x232, 0xff)
            self.Write_Reg(chip, 0x333, 0x01)

            self.Write_Reg(chip, 0x087, 0x62)
            self.Write_Reg(chip, 0x088, 0xC9)
            self.Write_Reg(chip, 0x089, 0x0E)
            self.Write_Reg(chip, 0x08A, 0x12)
            self.Write_Reg(chip, 0x08D, 0x01)

            self.Write_Reg(chip, 0x1B0, 0x00)
            self.Write_Reg(chip, 0x1B9, 0x24)
            self.Write_Reg(chip, 0x1BC, 0x0D)
            self.Write_Reg(chip, 0x1BE, 0x02)
            self.Write_Reg(chip, 0x1BF, 0x8E)
            self.Write_Reg(chip, 0x1C0, 0x2A)
            self.Write_Reg(chip, 0x1C1, 0x2A)
            self.Write_Reg(chip, 0x1C4, 0x7E)

            self.Write_Reg(chip, 0x08B, 0x01)
            self.Write_Reg(chip, 0x085, 0x10)
            self.Write_Reg(chip, 0x08C, 0x02)

            self.Write_Reg(chip, 0x1B5, 0x09)
            self.Write_Reg(chip, 0x1BB, 0x13)
            self.Write_Reg(chip, 0x1C5, 0x06)
            self.Write_Reg(chip, 0x083, 0x10)

            self.Write_Reg(chip, 0x111, 0x20)
            self.Write_Reg(chip, 0x112, 0x00)
            self.Write_Reg(chip, 0x110, 0x80)
            self.Write_Reg(chip, 0x13C, 0x00)
            self.Write_Reg(chip, 0x13D, 0x08)

            self.Write_Reg(chip, 0x200, 0x00)
            self.Write_Reg(chip, 0x201, 0x00)
            self.Write_Reg(chip, 0x300, 0x01)
            self.Write_Reg(chip, 0x450, 0x00)
            self.Write_Reg(chip, 0x451, 0x00)
            self.Write_Reg(chip, 0x452, 0x00)
            self.Write_Reg(chip, 0x453, 0x83)
            self.Write_Reg(chip, 0x454, 0x00)
            self.Write_Reg(chip, 0x455, 0x1f)
            self.Write_Reg(chip, 0x456, 0x00)
            self.Write_Reg(chip, 0x457, 0x0f)
            self.Write_Reg(chip, 0x458, 0x2f)
            self.Write_Reg(chip, 0x459, 0x21)
            self.Write_Reg(chip, 0x45a, 0x80)
            self.Write_Reg(chip, 0x45d, 0x45)
            self.Write_Reg(chip, 0x46c, 0xFF)
            self.Write_Reg(chip, 0x476, 0x01)
            self.Write_Reg(chip, 0x47d, 0xFF)

            self.Write_Reg(chip, 0x2aa, 0xb7)
            self.Write_Reg(chip, 0x2ab, 0x87)
            self.Write_Reg(chip, 0x2b1, 0xb7)
            self.Write_Reg(chip, 0x2b2, 0x87)
            self.Write_Reg(chip, 0x2a7, 0x01)
            self.Write_Reg(chip, 0x2ae, 0x01)
            self.Write_Reg(chip, 0x314, 0x01)
            self.Write_Reg(chip, 0x230, 0x28)
            self.Write_Reg(chip, 0x206, 0x00)
            self.Write_Reg(chip, 0x206, 0x01)
            self.Write_Reg(chip, 0x289, 0x04)
            self.Write_Reg(chip, 0x284, 0x62)
            self.Write_Reg(chip, 0x285, 0xC9)
            self.Write_Reg(chip, 0x286, 0x0E)
            self.Write_Reg(chip, 0x287, 0x12)
            self.Write_Reg(chip, 0x28A, 0x7B)
            self.Write_Reg(chip, 0x28B, 0x00)
            self.Write_Reg(chip, 0x290, 0x89)
            self.Write_Reg(chip, 0x294, 0x24)
            self.Write_Reg(chip, 0x296, 0x03)
            self.Write_Reg(chip, 0x297, 0x0D)
            self.Write_Reg(chip, 0x299, 0x02)
            self.Write_Reg(chip, 0x29A, 0x8E)
            self.Write_Reg(chip, 0x29C, 0x2A)
            self.Write_Reg(chip, 0x29F, 0x78)
            self.Write_Reg(chip, 0x2A0, 0x06)
            self.Write_Reg(chip, 0x280, 0x01)

            self.Write_Reg(chip, 0x268, 0x22)
            self.Write_Reg(chip, 0x301, 0x01)
            if chip == 1:
                self.Write_Reg(chip, 0x304, 0x10)
                self.Write_Reg(chip, 0x305, 0x10)
                self.Write_Reg(chip, 0x306, 0x05)
                self.Write_Reg(chip, 0x307, 0x05)
            if chip == 2:
                self.Write_Reg(chip, 0x304, 0x10)
                self.Write_Reg(chip, 0x305, 0x10)
                self.Write_Reg(chip, 0x306, 0x04)
                self.Write_Reg(chip, 0x307, 0x04)
            self.Write_Reg(chip, 0x03a, 0x82)
            self.Write_Reg(chip, 0x03a, 0x81)
            self.Write_Reg(chip, 0x03a, 0xc1)

            time.sleep(0.2)
            # print('0x084', hex(self.Read_Reg(ch, 0x084)))

            self.Write_Reg(chip, 0x300, 0x01)
            self.Write_Reg(chip, 0x0e7, 0x38)
            self.Write_Reg(chip, 0x0ed, 0xa2)
            self.Write_Reg(chip, 0x0e8, 0x01)
            self.Write_Reg(chip, 0x0eD, 0xA2)
            self.Write_Reg(chip, 0x0e9, 0x01)
            self.Write_Reg(chip, 0x0e9, 0x03)

            cnt = 0
            while cnt < 100:
                cal_stat = self.Read_Reg(chip, 0x0E9)
                if ((cal_stat & 0xF0) == 0x80):
                    break
                cnt += 1

            self.Write_Reg(chip, 0x0e8, 0x04)
            self.Write_Reg(chip, 0x0eD, 0xA2)
            self.Write_Reg(chip, 0x0e9, 0x01)
            self.Write_Reg(chip, 0x0e9, 0x03)

            cnt = 0
            while cnt < 100:
                cal_stat = self.Read_Reg(chip, 0x0E9)
                if ((cal_stat & 0xF0) == 0x80):
                    break
                cnt += 1

            self.Write_Reg(chip, 0x0e7, 0x30)

            self.Write_Reg(chip, 0x135, 0x00)
            self.Write_Reg(chip, 0x136, 0xC9)
            self.Write_Reg(chip, 0x137, 0xF0)
            self.Write_Reg(chip, 0x13A, 0x00)
            self.Write_Reg(chip, 0x040, 0x02)
            self.Write_Reg(chip, 0x041, 0x00)
            self.Write_Reg(chip, 0x044, 0x02)
            self.Write_Reg(chip, 0x045, 0x00)
            self.Write_Reg(chip, 0x03a, 0x82)
            self.Write_Reg(chip, 0x2a5, 0x01)
            # print('0x147', hex(self.Read_Reg(ch, 0x147)))
