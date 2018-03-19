# QuLab

QuLab 需要在 Jupyter Notebook 中使用。

## 准备工作

1. 安装 MongoDB，用于存储数据、历史代码、仪器配置、用户信息。
2. 制作 ssl 证书，用于 InstrumentServer 加密。

## 安装

```bash
python -m pip install QuLab
```
或者
```bash
git clone https://github.com/feihoo87/QuLab.git
cd QuLab
make
python -m pip install .
```

创建配置文件 `config.yaml`，若使用 Windows 系统，将其置于`%ProgramData%\QuLab\`路径下。

```yaml
ca_cert: &ca_cert /path/to/CACert/ca.pem

db:
  db: lab
  host: [10.122.7.18, 10.122.7.19, 10.122.7.20]
  username: lab_admin
  password: 'lab_password'
  authentication_source: lab
  replicaSet: rs0
  ssl: true
  ssl_ca_certs: *ca_cert
  ssl_match_hostname: true

db_local:
  db: lab
  host: localhost

db_dev:
  db: lab_dev
  host: localhost

server_port: 8123
server_name: ['localhost', '127.0.0.1', '10.122.7.18']
ssl:
  ca: *ca_cert
  cert: /path/to/sslcert/server.crt
  key: /path/to/sslkey/server.key
```

## 使用

### 创建初始用户

```python
from lab.admin import register
register()
```

### 登陆系统

```python
import lab
lab.login()
```

### 创建并运行简单 App

定义 App

```python
import numpy as np
import asyncio
import lab

class TestApp(lab.Application):
    '''一个简单的 App'''
    async def work(self):
        async for x in self.sweep['x']:
            yield x, np.random.randn()

    async def set_x(self, x):
        await asyncio.sleep(0.5)
        # print('x =', x)

    @staticmethod
    def plot(fig, data):
        x, y = data
        ax = fig.add_subplot(111)
        ax.plot(x, y)
        ax.set_xlabel('x (a.u.)')
        ax.set_ylabel('y (a.u.)')
```
将其提交到数据库
```python
TestApp.save()
```
一旦将App提交到数据库，以后就不必重复将代码复制过来运行了。直接配置并运行即可。
```python
import lab
import numpy as np

app = lab.make_app('TestApp').sweep([
    ('x', np.linspace(0, 1, 11))
])
lab.make_figure_for_app(app)
app.run()
```

### 创建复杂一点的 App

```python
import numpy as np
import asyncio
import lab

class ComplexApp(lab.Application):
    '''一个复杂点的 App'''
    async def work(self):
        async for y in self.sweep['y']:
            # 一定要注意设置 parent
            app = lab.make_app('TestApp', parent=self)
            x, z = await app.done()
            yield x, y, z

    async def set_y(self, y):
        await asyncio.sleep(0.5)
        # print('x =', x)

    def pre_save(self, x, y, z):
        if self.data.rows > 1:
            x = x[0]
        return x, y, z

    @staticmethod
    def plot(fig, data):
        x, y, z = data
        ax = fig.add_subplot(111)
        try:
            ax.imshow(z, extend=(min(x), max(x), min(y), max(y)))
        except:
            pass
        ax.set_xlabel('x (a.u.)')
        ax.set_ylabel('y (a.u.)')
```
保存
```python
ComplexApp.save()
```
运行

```python
import lab
import numpy as np

app = lab.make_app('ComplexApp').sweep([
    ('x', np.linspace(0, 1, 11)),
    ('y', np.linspace(3,5,11))
])
lab.make_figure_for_app(app)
app.run()
```

### 涉及到仪器操作

添加仪器设置
```python
# 第一台网分
lab.admin.setInstrument('PNA-I', 'localhost', 'TCPIP::10.122.7.250', 'NetworkAnalyzer')
# 第二台网分
lab.admin.setInstrument('PNA-II', 'localhost', 'TCPIP::10.122.7.251', 'NetworkAnalyzer')
```

查看已存在的仪器

```python
lab.listInstruments()
```

定义 App
```python
import numpy as np
import skrf as rf
from lab import Application


class GetPNAS21(Application):
    '''从网分上读取 S21

    require:
        rc : PNA
        settings: repeat(optional)

    return: Frequency, Re(S21), Im(S21)
    '''
    async def work(self):
        if self.params.get('power', None) is None:
            self.params['power'] = [self.rc['PNA'].getValue('Power'), 'dBm']
        x = self.rc['PNA'].get_Frequency()
        for i in range(self.settings.get('repeat', 1)):
            self.processToChange(100.0 / self.settings.get('repeat', 1))
            y = np.array(self.rc['PNA'].get_S())
            yield x, np.real(y), np.imag(y)
            self.increaseProcess()

    def pre_save(self, x, re, im):
        if self.status['result']['rows'] > 1:
            x = x[0]
            re = np.mean(re, axis=0)
            im = np.mean(im, axis=0)
        return x, re, im

    @staticmethod
    def plot(fig, obj):
        x, re, im = obj
        s = re + 1j * im
        ax = fig.add_subplot(111)
        ax.plot(x / 1e9, rf.mag_2_db(np.abs(s)))
        ax.set_xlabel('Frequency / GHz')
        ax.set_ylabel('S21 / dB')
```
保存
```python
GetPNAS21.save()
```
运行
```python
import lab

app = lab.make_app('GetPNAS21').with_rc({
    'PNA': 'PNA-II'     # PNA-II 必须是已经添加到数据库里的设备名
}).with_settings({
    'repeat': 10
}).with_params(
    power = [-27, 'dBm'],
    att = [-30, 'dB']
).with_tags('5 bits sample', 'Cavity 1')

lab.make_figure_for_app(app)

app.run()
```

### 查询

查看已有的 App
```python
lab.listApps()
```

查询数据
```python
results = lab.query()
results.display()
print('%d results found.' % results.count())
```

获取原始数据

```python
res = lab.query(app='TestApp')
x,y = res[0].data

import matplotlib.pyplot as plt
plt.plot(x, y)
plt.show()
```

## License

[MIT](https://opensource.org/licenses/MIT)
