import TimeDomainPlotCore as ad_core
# 初始化
ad_core.Initialize()
ad_core.setTriggerType(1)

length = 2
frame_num = 3

# 设置响应触发次数
ad_core.setRecordLength(length)
ad_core.setFrameNumber(frame_num)


# 启动采集
ad_core.startCapture()

# 此处触发源应当发送触发信号，否则下面的代码会无限等待

# 读回数据
data = ad_core.getData()
print ("Receive Data Length: ",  len(data),  len(data[0]), len(data[1]))

# print(data[0])
import matplotlib.pyplot as plt
for i in range(3):
    plt.figure(1)
    plt.plot(data[0][0])
    plt.show()
