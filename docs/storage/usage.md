# qulab.storage 使用文档

## 快速开始

### 安装

```bash
pip install qulab
```

### 基本用法

```python
from qulab.storage import LocalStorage

# 创建存储实例
storage = LocalStorage("~/.qulab/storage")

# 创建文档
doc_ref = storage.create_document(
    name="calibration",
    data={"f01": 5.2e9, "t1": 100e-6},
    state="ok",
    tags=["calibration", "qubit"]
)

# 加载文档
doc = doc_ref.get()
print(doc.data)  # {'f01': 5200000000.0, 't1': 0.0001}
```

## 存储类型

### LocalStorage

本地文件存储，使用 SQLite 存储元数据，文件系统存储数据。

```python
from qulab.storage import LocalStorage
from pathlib import Path

# 创建存储
storage = LocalStorage("/path/to/storage")

# 或使用默认位置
storage = LocalStorage(Path.home() / ".qulab" / "storage")

# 自定义数据库 URL
storage = LocalStorage(
    base_path="/path/to/storage",
    db_url="postgresql://user:pass@localhost/qulab"
)
```

### RemoteStorage

远程存储客户端，通过 ZMQ 连接远程服务器。

```python
from qulab.storage import RemoteStorage

# 连接到远程服务器
storage = RemoteStorage("tcp://192.168.1.100:6789")

# 使用超时
storage = RemoteStorage(
    server_address="tcp://192.168.1.100:6789",
    timeout=60.0
)

# 使用与 LocalStorage 相同的 API
doc_ref = storage.create_document(name="test", data={"value": 42})
```

## 文档操作

### 创建文档

```python
# 基本文档
doc_ref = storage.create_document(
    name="qubit_cal",
    data={"f01": 5.2e9, "t1": 100e-6},
    state="ok",  # 'ok', 'error', 'warning', 'unknown'
    tags=["calibration", "qubit"]
)

# 带额外元数据
doc_ref = storage.create_document(
    name="experiment",
    data={"results": [...]},
    state="ok",
    tags=["experiment", "2024"],
    author="user1",
    project="project_a"
)

# 带分析代码的文档
doc_ref = storage.create_document(
    name="resonator_analysis",
    data={"fit_result": {"f0": 5.001e9, "Q": 10000}},
    state="ok",
    tags=["analysis", "resonator"],
    script='''
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

def lorentzian(f, f0, Q, A, offset):
    return A / (1 + 4*Q**2*((f-f0)/f0)**2) + offset

# 拟合数据
popt, _ = curve_fit(lorentzian, freq, amplitude, p0=[5e9, 10000, 1, 0])
print(f"Resonator frequency: {popt[0]/1e9:.3f} GHz")
print(f"Quality factor: {popt[1]:.0f}")
'''
)

# 访问文档的分析代码
doc = doc_ref.get()
print(doc.script_hash)  # SHA1 哈希值
print(doc.script)       # 完整的分析代码（延迟加载）
```

**设计说明：**
- `script`: 分析代码，使用内容寻址存储，相同代码自动去重
- 延迟加载：代码仅在访问 `doc.script` 时从存储读取
- 适合存储生成此文档的分析/处理代码，便于结果复现

### 获取文档

```python
# 通过引用获取
doc = doc_ref.get()
print(doc.name)
print(doc.data)
print(doc.tags)
print(doc.state)
print(doc.ctime)  # 创建时间
print(doc.mtime)  # 修改时间
print(doc.atime)  # 访问时间

# 通过 ID 获取
doc = storage.get_document(123)
```

### 查询文档

```python
# 查询所有文档
results = list(storage.query_documents())

# 按名称查询
results = list(storage.query_documents(name="calibration"))

# 按名称模式查询
results = list(storage.query_documents(name="cal*"))

# 按标签查询
results = list(storage.query_documents(tags=["calibration"]))
results = list(storage.query_documents(tags=["calibration", "qubit"]))

# 按状态查询
results = list(storage.query_documents(state="ok"))

# 按时间范围查询
from datetime import datetime, timedelta
results = list(storage.query_documents(
    after=datetime.now() - timedelta(days=7)
))

# 分页查询
results = list(storage.query_documents(offset=0, limit=10))

# 组合查询
results = list(storage.query_documents(
    name="cal*",
    tags=["qubit"],
    state="ok",
    limit=100
))
```

### 计数文档

```python
# 计数所有文档
count = storage.count_documents()

# 按条件计数
count = storage.count_documents(tags=["calibration"])
count = storage.count_documents(state="error")
```

### 更新文档

```python
# 获取文档
doc = storage.get_document(123)

# 修改数据
doc.data["new_key"] = "new_value"
doc.state = "ok"

# 保存为新版本（创建新文档，保留原版本）
new_ref = doc.save(storage)
print(f"New version ID: {new_ref.id}")
print(f"Parent ID: {doc.id}")
```

### 删除文档

```python
# 删除单个文档
doc_ref.delete()

# 或通过 ID 删除
from qulab.storage.local import DocumentRef
DocumentRef(123, storage).delete()
```

### 文档与数据集关联

一个 Document 可以关联多个 Dataset（表示由这些数据集分析得来），一个 Dataset 也可以关联多个 Document（表示被多次分析）。

```python
# 创建数据集
ds_ref1 = storage.create_dataset(name="raw_data_1", description={"type": "raw"})
ds_ref2 = storage.create_dataset(name="raw_data_2", description={"type": "raw"})

# 创建文档并关联数据集
doc_ref = storage.create_document(
    name="analysis_result",
    data={"fit_result": "..."},
    state="ok",
    tags=["analysis"],
    datasets=[ds_ref1.id, ds_ref2.id]  # 关联数据集
)

# 获取文档及其关联的数据集
doc = doc_ref.get()
for dataset in doc.datasets:
    print(f"Derived from dataset: {dataset.name}")

# 获取数据集及其关联的文档
ds = ds_ref1.get()
for document in ds.documents:
    print(f"Analyzed by document: {document.name}")
```

## 数据集操作

### 创建数据集

```python
# 创建数据集
ds_ref = storage.create_dataset(
    name="scan1",
    description={
        "app": "scan",
        "parameters": {"start": 0, "stop": 10, "step": 0.1},
        "comment": "Qubit frequency scan"
    }
)

# 获取数据集对象
ds = ds_ref.get()
```

### 创建带配置和代码的数据集

```python
# 实验配置（多层嵌套字典）
config = {
    "qubit": "Q1",
    "frequency": {
        "start": 5.0e9,
        "stop": 5.1e9,
        "points": 101
    },
    "power": {
        "drive": -20,  # dBm
        "readout": -30  # dBm
    },
    "averages": 1000
}

# 数据采集代码
measurement_script = '''
import numpy as np
from qulab import mw_source, digitizer

def measure(freq, power_drive, power_readout, averages):
    mw_source.set_frequency(freq)
    mw_source.set_power(power_drive)
    # ... 测量逻辑
    data = digitizer.acquire(averages)
    return np.mean(data), np.std(data)
'''

# 创建带配置和代码的数据集
ds_ref = storage.create_dataset(
    name="qubit_resonator_scan",
    description={"type": "resonator_scan", "qubit": "Q1"},
    config=config,      # 实验配置（内容寻址去重存储）
    script=measurement_script  # 采集代码（内容寻址去重存储）
)

# 获取数据集
ds = ds_ref.get()

# 访问配置（延迟加载）
print(ds.config_hash)  # SHA1 哈希值
print(ds.config["frequency"]["start"])  # 5.0e9
print(ds.config["power"]["drive"])      # -20

# 访问代码（延迟加载）
print(ds.script_hash)  # SHA1 哈希值
print(ds.script[:100])  # 代码前100字符
```

**设计说明：**
- `config`: 实验配置参数，使用内容寻址存储，相同配置自动去重
- `script`: 数据采集代码，使用内容寻址存储，相同代码自动去重
- 两者都是延迟加载，仅在访问时从 chunk 存储读取
- 配置和代码的哈希值可通过 `config_hash` 和 `script_hash` 获取

### 追加数据

```python
# 追加单个数据点
ds.append(
    position=(0, 0),  # (level, step)
    data={"frequency": 5.2e9, "amplitude": 0.5}
)

# 追加多个值
ds.append(
    position=(0, 1),
    data={"frequency": 5.21e9, "amplitude": 0.6, "phase": 0.1}
)

# 刷新到磁盘
ds.flush()
```

### 获取数组

```python
# 获取所有数组键
keys = ds.keys()
print(keys)  # ['frequency', 'amplitude', 'phase']

# 获取数组
freq_array = ds.get_array("frequency")
amp_array = ds.get_array("amplitude")

# 转换为 numpy 数组
freq_data = freq_array.toarray()
print(freq_data.shape)
```

### 数组操作

```python
# 获取数组
arr = ds.get_array("frequency")

# 迭代所有数据点
for pos, value in arr.iter():
    print(f"Position: {pos}, Value: {value}")

# 获取所有值
values = arr.value()

# 获取所有位置
positions = arr.positions()

# 获取位置和值
positions, values = arr.items()

# NumPy 风格切片
subset = arr[0:10, 0:5]
single = arr[5, 3]
```

### 查询数据集

```python
# 查询所有数据集
results = list(storage.query_datasets())

# 按名称查询
results = list(storage.query_datasets(name="scan1"))

# 按名称模式查询
results = list(storage.query_datasets(name="scan*"))

# 按标签查询
results = list(storage.query_datasets(tags=["experiment"]))

# 按时间范围查询
from datetime import datetime, timedelta
results = list(storage.query_datasets(
    after=datetime.now() - timedelta(days=7)
))

# 分页
results = list(storage.query_datasets(offset=0, limit=10))
```

### 删除数据集

```python
# 删除数据集
ds_ref.delete()

# 或通过 ID 删除
from qulab.storage.local import DatasetRef
DatasetRef(123, storage).delete()
```

## CLI 使用

### 启动存储服务器

```bash
# 启动服务器
python -m qulab.storage server start --port 6789 --data-path ~/.qulab/storage

# 指定主机
python -m qulab.storage server start --host 0.0.0.0 --port 6789
```

### 文档操作

```bash
# 创建文档
echo '{"value": 42}' | python -m qulab.storage doc create my_doc --state ok --tag test

# 创建带分析代码的文档
python -m qulab.storage doc create analysis_report \
    --state ok \
    --tag analysis \
    --script 'import matplotlib.pyplot as plt; plt.plot([1,2,3])'

# 从文件读取分析代码
python -m qulab.storage doc create analysis_report \
    --script '@analysis.py'

# 获取文档
python -m qulab.storage doc get 123

# 获取文档（包含代码内容）
python -m qulab.storage doc get 123 --show-script

# 以 JSON 格式输出
python -m qulab.storage doc get 123 --json-output

# 查询文档
python -m qulab.storage doc query --name "cal*" --tag calibration --limit 10

# 删除文档
python -m qulab.storage doc delete 123
```

### 数据集操作

```bash
# 创建数据集
python -m qulab.storage dataset create my_scan --desc '{"app": "test"}'

# 创建带配置的数据集
python -m qulab.storage dataset create resonator_scan \
    --desc '{"type": "resonator", "qubit": "Q1"}' \
    --config '{"freq": {"start": 5.0e9, "stop": 5.1e9}, "power": -20}'

# 创建带配置和采集代码的数据集
python -m qulab.storage dataset create qubit_scan \
    --desc '{"type": "qubit"}' \
    --config '{"freq": 5e9, "averages": 1000}' \
    --script 'import numpy as np; print(np.sin(0.5))'

# 从文件读取采集代码
python -m qulab.storage dataset create my_experiment \
    --config '@experiment_config.json' \
    --script '@measurement.py'

# 查看数据集信息
python -m qulab.storage dataset info 123

# 查看数据集信息（包含配置内容）
python -m qulab.storage dataset info 123 --show-config

# 查看数据集信息（包含代码内容）
python -m qulab.storage dataset info 123 --show-script

# 同时查看配置和代码
python -m qulab.storage dataset info 123 --show-config --show-script

# 查询数据集
python -m qulab.storage dataset query --name "scan*" --limit 10

# 删除数据集
python -m qulab.storage dataset delete 123
```

## 高级用法

### 自定义存储路径

```python
from pathlib import Path

# 使用 XDG 标准路径
import os
data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
storage = LocalStorage(data_home / "qulab")
```

### 批量操作

```python
# 批量创建文档
for i in range(100):
    storage.create_document(
        name=f"exp_{i:03d}",
        data={"index": i},
        tags=["batch", "experiment"]
    )

# 批量查询
docs = list(storage.query_documents(
    name="exp_*",
    tags=["batch"],
    limit=1000
))
```

### 数据集批量追加

```python
import numpy as np

# 创建数据集
ds_ref = storage.create_dataset("sweep", {"dimensions": [100, 100]})
ds = ds_ref.get()

# 批量追加数据
for i in range(100):
    for j in range(100):
        ds.append(
            position=(i, j),
            data={
                "x": i * 0.1,
                "y": j * 0.1,
                "z": np.sin(i * 0.1) * np.cos(j * 0.1)
            }
        )
        # 定期刷新
        if (i * 100 + j) % 1000 == 0:
            ds.flush()

ds.flush()
```

### 远程存储使用

```python
from qulab.storage import RemoteStorage

# 连接远程服务器
storage = RemoteStorage("tcp://192.168.1.100:6789")

# 检查连接
try:
    count = storage.count_documents()
    print(f"Remote storage has {count} documents")
except Exception as e:
    print(f"Connection failed: {e}")

# 使用与本地存储相同的 API
doc_ref = storage.create_document(
    name="remote_doc",
    data={"value": 42},
    state="ok"
)

# 获取文档（从远程服务器获取）
doc_data = doc_ref.get()
```

## 配置

### 配置文件

创建 `~/.qulab/config.ini`：

```ini
[storage]
data = ~/.qulab/storage
server_port = 6789

[storage.server]
host = 127.0.0.1
port = 6789
```

### 环境变量

```bash
# 设置默认存储路径
export QULAB_STORAGE_PATH="/path/to/storage"

# 设置远程服务器
export QULAB_STORAGE_SERVER="tcp://192.168.1.100:6789"
```

## 最佳实践

### 1. 文档命名与配置管理

使用有意义的名称、标签和配置：

```python
# 好的实践：详细的配置和代码跟踪
ds = storage.create_dataset(
    name="qubit_01_resonator_scan_20240222",
    description={"type": "resonator_scan", "qubit": "Q1"},
    config={
        "frequency": {"start": 5.0e9, "stop": 5.1e9, "points": 101},
        "power": {"drive": -20, "readout": -30},
        "averages": 1000
    },
    script="""
import numpy as np
from qulab import mw_source, digitizer

def measure(freq, power_drive, power_readout, averages):
    mw_source.set_frequency(freq)
    mw_source.set_power(power_drive)
    data = digitizer.acquire(averages)
    return np.mean(data), np.std(data)
"""
)

# 创建关联的分析文档
doc = storage.create_document(
    name="qubit_01_resonator_analysis_20240222",
    data={"fit_result": {"f0": 5.001e9, "Q": 10000}},
    state="ok",
    tags=["analysis", "qubit_01", "resonator"],
    script="""
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

# 加载数据集并分析
# ...
"""
)

# 避免
storage.create_dataset(name="scan1", description={"type": "test"})
```

### 2. 状态管理

使用状态跟踪文档质量：

```python
# 校准成功
doc = storage.create_document(..., state="ok")

# 数据有问题
doc = storage.create_document(..., state="error", tags=["bad_data"])

# 需要重新校准
doc = storage.create_document(..., state="warning")
```

### 3. 定期清理

```python
from datetime import datetime, timedelta

# 查找旧文档
old_docs = list(storage.query_documents(
    before=datetime.now() - timedelta(days=365)
))

# 选择性删除
for doc_ref in old_docs:
    doc = doc_ref.get()
    if doc.state == "error":
        doc_ref.delete()
```

### 4. 配置和代码复用

利用内容寻址存储实现配置和代码复用：

```python
# 定义标准配置
standard_config = {
    "frequency": {"start": 5.0e9, "stop": 5.1e9, "points": 101},
    "power": {"drive": -20, "readout": -30},
    "averages": 1000
}

# 多个数据集使用相同配置（自动去重）
ds1 = storage.create_dataset(
    name="qubit_01_scan",
    description={"qubit": "Q1"},
    config=standard_config
)
ds2 = storage.create_dataset(
    name="qubit_02_scan",
    description={"qubit": "Q2"},
    config=standard_config  # 复用相同配置
)

# 验证去重
print(ds1.config_hash == ds2.config_hash)  # True

# 共享分析代码
analysis_code = '''
import numpy as np
from scipy.optimize import curve_fit

def analyze_resonator(freq, amplitude):
    # 分析代码...
    return fit_result
'''

# 多个文档使用相同分析代码
doc1 = storage.create_document(
    name="analysis_1",
    data={"result": "..."},
    script=analysis_code
)
doc2 = storage.create_document(
    name="analysis_2",
    data={"result": "..."},
    script=analysis_code  # 复用相同代码
)

print(doc1.script_hash == doc2.script_hash)  # True
```

### 5. 数据备份

```python
import shutil
from datetime import datetime

# 备份存储目录
backup_dir = f"backup_{datetime.now():%Y%m%d}"
shutil.copytree(storage.base_path, backup_dir)
```

## 故障排除

### 数据库锁定

```python
# 如果出现数据库锁定错误，检查是否有其他进程正在使用
# 使用 lsof 检查
# lsof ~/.qulab/storage/storage.db
```

### 远程连接失败

```python
# 检查服务器是否运行
from qulab.storage.remote import RemoteStorage

storage = RemoteStorage("tcp://localhost:6789", timeout=5.0)
try:
    storage.count_documents()
    print("Connected")
except Exception as e:
    print(f"Failed: {e}")
    # 检查服务器
    # python -m qulab.storage server status
```

### 数据损坏

```python
# 如果数据损坏，可以尝试从 chunk 恢复
from qulab.storage.chunk import load_chunk

try:
    data = load_chunk(chunk_hash, base_path=storage.base_path)
except Exception as e:
    print(f"Chunk corrupted: {e}")
```

## API 参考

### Storage 类

| 方法 | 说明 |
|------|------|
| `create_document(name, data, state, tags, script, **meta)` | 创建文档 |
| `get_document(id)` | 获取文档 |
| `query_documents(**filters)` | 查询文档 |
| `count_documents(**filters)` | 计数文档 |
| `create_dataset(name, description, config, script)` | 创建数据集 |
| `get_dataset(id)` | 获取数据集 |
| `query_datasets(**filters)` | 查询数据集 |
| `count_datasets(**filters)` | 计数数据集 |

**新增参数说明：**
- `create_dataset(config, script)`: 支持传入实验配置和采集代码
  - `config`: 字典类型，实验配置参数（内容寻址去重存储）
  - `script`: 字符串类型，采集代码（内容寻址去重存储）
- `create_document(script)`: 支持传入分析代码
  - `script`: 字符串类型，生成此文档的分析代码（内容寻址去重存储）

### Document 类

| 属性 | 说明 |
|------|------|
| `id` | 文档 ID |
| `name` | 文档名称 |
| `data` | 文档数据（延迟加载） |
| `meta` | 元数据 |
| `tags` | 标签列表 |
| `state` | 状态 |
| `script` | 分析代码字符串（延迟加载） |
| `script_hash` | 代码的 SHA1 哈希值 |
| `ctime` | 创建时间 |
| `mtime` | 修改时间 |
| `atime` | 访问时间 |

**延迟加载属性说明：**
- `data`: 文档数据，仅在首次访问时从 chunk 存储读取
  - 优点：访问文档元数据（如 `name`, `tags`, `state`）时不会加载大量数据
  - 适合存储大型分析结果数据
- `script` / `script_hash`: 访问分析代码，代码使用内容寻址存储实现去重
  - 延迟加载：代码仅在首次访问 `script` 时从 chunk 存储读取
  - 适合存储生成此文档的分析/处理代码，便于结果复现

### Dataset 类

| 属性/方法 | 说明 |
|------|------|
| `keys()` | 获取数组键列表 |
| `get_array(key)` | 获取数组 |
| `create_array(key, inner_shape)` | 创建数组 |
| `append(position, data)` | 追加数据 |
| `flush()` | 刷新到磁盘 |
| `config` | 实验配置字典（延迟加载） |
| `config_hash` | 配置的 SHA1 哈希值 |
| `script` | 采集代码字符串（延迟加载） |
| `script_hash` | 代码的 SHA1 哈希值 |

**内容寻址属性说明：**
- `config` / `config_hash`: 访问实验配置，配置使用内容寻址存储实现去重
- `script` / `script_hash`: 访问采集代码，代码使用内容寻址存储实现去复
- 两者均为延迟加载，仅在首次访问时从 chunk 存储读取
- 通过哈希值可以判断两个 Dataset 是否使用相同的配置或代码

### Array 类

| 方法 | 说明 |
|------|------|
| `iter()` | 迭代数据点 |
| `value()` | 获取所有值 |
| `positions()` | 获取所有位置 |
| `items()` | 获取位置和值 |
| `toarray()` | 转换为 numpy 数组 |
| `__getitem__()` | 切片访问 |
