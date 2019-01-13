from AWG import AWGboard, Waveform

# 使用最新的qulab_toolbox，https://github.com/Lagikna/QuLab_toolbox
# from QuLab_toolbox.qulab_toolbox.wavedata import *
# import numpy as np
# import matplotlib.pyplot as plt

#产生基本波形，Wavedata类
#a=Gaussian(width=2e-6,sRate=2e9)
#b=Blank(width=2e-6,sRate=2e9)
#c=Blank(width=0.5e-6,sRate=2e9)
#d=DC(width=2e-6,sRate=2e9)

#print(len(a.data),len(b.data),len(c.data),len(d.data))
#组合波形，Wavedata类
#i=c|a|b|a|b|a|c
#q=c|b|d|b|d|b|c

# 使用vIQmixer进行上变频，加载到200MHz的载波上,seq也是Wavedata类
#seq=vIQmixer.up_conversion(200e6,I=i,Q=q)

def awg_example(ip):
    """AWG单元有多个通道组成，其基本工作原理是通过网络与FPGA通信，将AWG配置参数设置完成后即可进入工作状态。
    在正常工作状态下可以调节的参数有通道增益，通道默认输出电压值，通道输出循环次数。
    AWG的波形输出分为波形数据区和指令数据区，用户在使用时，通过上位机设置自己想要设置的通道的波形数据区和指令数据区，
    然后设置启动命令，即可启动该通道的波形输出控制，如果指令数据区第一条指令是触发型指令，即可实现波形数据的触发同步输出。
    所以AWG提供了一种简单，灵活易用的使用接口：

    一般为以下步骤::

        -连接设备
        -初始化设备
        -打印AWG参数信息[可选]
        -准备波形数据
            -根据需要生成或加载一段或多段波形，设置每段波形的输出类型，输出时间
            -编译合成波形数据
        -预览预期的波形输出[可选]
        -启动通道输出
        -断开设备连接

    样例代码::

        from AWG import AWGboard, Waveform
        awg = AWGboard.AWGBoard()
        awg.connect(ip)
        # 初始化AWG
        awg.InitBoard()

        # 显示AWG当前参数
        awg.display_AWG()

        # 波形准备与生成
        wave_list = []
        # 波形对象
        wave_ctrl = Waveform.Waveform()
        # 第一段波形
        wave_ctrl.generate_sin(period=100e-9, amp=1)  # 生成周期为100ns的正弦信号
        wave_ctrl.wave =seq.data
        # print(len(seq.data))
        wave_ctrl.write_wave_file('test.wave')  # 写波形文件，测试用的
        wave_list.append(awg.gen_wave_unit(wave_ctrl.wave, '触发', 0))
        # # 第二段波形
        wave_ctrl.generate_squr(period=50e-9, high=1, low=-0.6)  # 生成周期为50ns的方波信号
        wave_list.append(awg.gen_wave_unit(wave_ctrl.wave, '延时', len(seq.data)*1e-9))  # 2us时刻输出波形
        # # 第三段波形
        filename = "test.wave"
        wave_ctrl.load_wave_file(filename)  # 通过文件加载波形
        wave_list.append(awg.gen_wave_unit(wave_ctrl.wave, '延时', len(seq.data)*1e-9+1e-6))  # 5us时刻输出波形

        # 重复5次输出
        # wave_list *= 5

        awg_ch = 2
        # 编译合成波形到AWG 通道awg_ch
        awg.wave_compile(awg_ch, wave_list)

        # 默认时 is_continue为False, 可以不加, 如果要将编译的波形强制为连续周期性的输出，可以设置is_continue=True
        # awg.wave_compile(awg_ch, wave_list, is_continue=True)

        # 预览通道awg_ch的波形
        # user_set_xlabel=False时matplotlib图像交互时可以看到x轴坐标的细节，但是没有单位信息
        # is_volt = True 表示以电压的形式显示， = False表示以码值的形式显示
        wave_ctrl.wave_preview(ch=awg_ch, awg=awg, is_volt=True, user_set_xlabel=True)

        # 以下是生成一段连续的波形，预览波形输出
        wave_ctrl.generate_sin(period=10e-9, amp=0.25)  # 生成周期为100ns的正弦信号
        # wave_ctrl.generate_dc(volt=0)
        wave_ctrl.wave_preview(is_volt=True, user_set_xlabel=True)

        # 将波形编译成连续波形输出
        wave_list = [awg.gen_wave_unit(wave_ctrl.wave, '触发', 0)]
        awg.wave_compile(1, wave_list, is_continue=True)  # 显式指明生成连续波形，此时的触发标识无效
        awg.wave_compile(2, wave_list, is_continue=True)  # 显式指明生成连续波形，此时的触发标识无效
        awg.wave_compile(3, wave_list, is_continue=True)  # 显式指明生成连续波形，此时的触发标识无效
        awg.wave_compile(4, wave_list, is_continue=True)  # 显式指明生成连续波形，此时的触发标识无效
        # wave_ctrl.wave_preview(ch=awg_ch, awg=awg, is_volt=False, user_set_xlabel=False)

        awg.Start(15)  # 0xF使能4个通道输出， 如果指令集第一条是触发类型，则外部触发到达时AWG就会输出相应波形
        awg.disconnect()
    """
    awg = AWGboard.AWGBoard()
    awg.connect(ip)
    # 初始化AWG
    awg.InitBoard()

    # 显示AWG当前参数
    awg.display_AWG()

    # 波形准备与生成
    wave_list = []
    # 波形对象
    wave_ctrl = Waveform.Waveform()
    # 第一段波形
    wave_ctrl.generate_sin(period=100e-9, amp=1)  # 生成周期为100ns的正弦信号
    wave_ctrl.wave =seq.data
    # print(len(seq.data))
    wave_ctrl.write_wave_file('test.wave')  # 写波形文件，测试用的
    wave_list.append(awg.gen_wave_unit(wave_ctrl.wave, '触发', 0))
    # # 第二段波形
    wave_ctrl.generate_squr(period=50e-9, high=1, low=-0.6)  # 生成周期为50ns的方波信号
    wave_list.append(awg.gen_wave_unit(wave_ctrl.wave, '延时', len(seq.data)*1e-9))  # 2us时刻输出波形
    # # 第三段波形
    filename = "test.wave"
    wave_ctrl.load_wave_file(filename)  # 通过文件加载波形
    wave_list.append(awg.gen_wave_unit(wave_ctrl.wave, '延时', len(seq.data)*1e-9+1e-6))  # 5us时刻输出波形

    # 重复5次输出
    # wave_list *= 5

    awg_ch = 2
    # 编译合成波形到AWG 通道awg_ch
    awg.wave_compile(awg_ch, wave_list)

    # 默认时 is_continue为False, 可以不加, 如果要将编译的波形强制为连续周期性的输出，可以设置is_continue=True
    # awg.wave_compile(awg_ch, wave_list, is_continue=True)

    # 预览通道awg_ch的波形
    # user_set_xlabel=False时matplotlib图像交互时可以看到x轴坐标的细节，但是没有单位信息
    # is_volt = True 表示以电压的形式显示， = False表示以码值的形式显示
    wave_ctrl.wave_preview(ch=awg_ch, awg=awg, is_volt=True, user_set_xlabel=True)

    # 以下是生成一段连续的波形，预览波形输出
    # wave_ctrl.generate_sin(period=10e-9, amp=0.25)  # 生成周期为100ns的正弦信号
    wave_ctrl.generate_dc(volt=0)
    wave_ctrl.wave_preview(is_volt=True, user_set_xlabel=True)

    # 将波形编译成连续波形输出
    wave_list = [awg.gen_wave_unit(wave_ctrl.wave, '触发', 0)]
    awg.wave_compile(1, wave_list, is_continue=True)  # 显式指明生成连续波形，此时的触发标识无效
    awg.wave_compile(2, wave_list, is_continue=True)  # 显式指明生成连续波形，此时的触发标识无效
    awg.wave_compile(3, wave_list, is_continue=True)  # 显式指明生成连续波形，此时的触发标识无效
    awg.wave_compile(4, wave_list, is_continue=True)  # 显式指明生成连续波形，此时的触发标识无效
    # wave_ctrl.wave_preview(ch=awg_ch, awg=awg, is_volt=False, user_set_xlabel=False)

    awg.Start(15)  # 0xF使能4个通道输出， 如果指令集第一条是触发类型，则外部触发到达时AWG就会输出相应波形
    awg.disconnect()

    # plt.figure()
    # plt.plot(awg.waves[0])
    # plt.show()

if __name__ == '__main__':
    ip = '192.168.5.140'
    # ip = '192.168.1.8'
    awg_example(ip)
