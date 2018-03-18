# QuLab

QuLab 需要在 Jupyter Notebook 中使用。

## 准备工作

1. 安装 MongoDB，用于存储数据、历史代码、仪器配置、用户信息。
2. 制作 ssl 证书，用于 InstrumentServer 加密。

## 安装

```bash
python -m pip install QuLab
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
from lab import _bootstrap
from lab.admin import register
_bootstrap._connect_db()
register()
```

或者直接操作数据库

```python
from lab import _bootstrap
from lab.db._schema import User

_bootstrap._connect_db()

user = User(
    name='admin',
    email='admin@example.com',
    fullname = 'Fullname')
user.password = 'password'
user.save()
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

app = lab.make_app('TestApp').set_sweeps([
    ('x', np.linspace(0, 1, 11))
])
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

## License

[MIT](https://opensource.org/licenses/MIT)
