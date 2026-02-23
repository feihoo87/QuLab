# qulab.storage 设计文档

## 概述

`qulab.storage` 是 QuLab 的统一存储系统，整合了原有的分散存储功能：

- `qulab.executor.storage` - 工作流执行报告存储
- `qulab.scan.record` - 扫描数据存储
- `qulab.storage` - 已有基础架构

## 设计目标

1. **统一存储接口** - 提供一致的 API 用于文档和数据集存储
2. **本地与远程透明访问** - 相同的代码适用于本地和远程存储
3. **内容寻址存储** - 使用 SHA1 哈希实现数据去重
4. **版本控制** - 支持文档版本链
5. **标签系统** - 灵活的数据组织和查询
6. **配置与代码管理** - 内容寻址存储配置和代码，支持复用和追溯

## 核心概念

### 数据实体统一

| 现有概念 | 说明 | 新设计 |
|---------|------|--------|
| Report (executor) | 工作流执行报告，含状态、参数、原始数据 | **Document** - 通用文档存储 |
| Record (scan) | 扫描数据，含多维数组、配置、元数据 | **Dataset** - 扩展已有 Dataset |
| BufferList (scan) | 多维数组数据存储 | **Array** - 专用数组存储 |
| Config | 实验配置参数 | **Config** - 内容寻址配置存储 |
| Script | 实验/分析代码 | **Script** - 内容寻址代码存储 |

### 存储模式

所有存储支持两种模式：

1. **LocalStorage** - 本地文件系统直接访问
2. **RemoteStorage** - 通过 ZMQ API 访问远程服务器

## 架构设计

### 模块结构

```
qulab/storage/
├── __init__.py              # 公共 API 导出
├── base.py                  # 抽象基类定义 (Storage)
├── local.py                 # LocalStorage 实现
├── remote.py                # RemoteStorage 实现 (ZMQ client)
├── server.py                # StorageServer 实现 (ZMQ server)
├── document.py              # Document 类 (原 Report)
├── datastore.py             # Dataset 类 (扩展原 scan.record)
├── array.py                 # Array 类 (原 BufferList)
├── chunk.py                 # 内容寻址块存储
├── file.py                  # 文件格式 (已有)
├── cli.py                   # CLI 命令
└── models/                  # SQLAlchemy ORM 模型
    ├── __init__.py
    ├── base.py              # 基类和会话管理
    ├── config.py            # Config 模型 (内容寻址配置)
    ├── dataset.py           # Dataset 模型
    ├── document.py          # Document 模型
    ├── file.py              # File/FileChunk 模型
    ├── script.py            # Script 模型 (内容寻址代码)
    └── tag.py               # Tag 模型
```

### 核心类设计

#### Storage (base.py)

抽象基类定义所有存储实现的通用接口：

```python
class Storage(ABC):
    @property
    @abstractmethod
    def is_remote(self) -> bool: ...

    # Document API
    @abstractmethod
    def create_document(self, name, data, state, tags, **meta) -> DocumentRef: ...
    @abstractmethod
    def get_document(self, id: int) -> Document: ...
    @abstractmethod
    def get_latest_document(self, name: str, state: Optional[str] = None) -> Optional[DocumentRef]: ...
    @abstractmethod
    def query_documents(self, **filters) -> Iterator[DocumentRef]: ...
    @abstractmethod
    def count_documents(self, **filters) -> int: ...

    # Dataset API
    @abstractmethod
    def create_dataset(self, name, description) -> DatasetRef: ...
    @abstractmethod
    def get_dataset(self, id: int) -> Dataset: ...
    @abstractmethod
    def query_datasets(self, **filters) -> Iterator[DatasetRef]: ...
    @abstractmethod
    def count_datasets(self, **filters) -> int: ...
```

#### LocalStorage (local.py)

本地文件存储实现，使用 SQLite 存储元数据，文件系统存储数据：

```python
class LocalStorage(Storage):
    def __init__(self, base_path: str | Path, db_url: Optional[str] = None):
        # 初始化目录结构
        # - base_path/documents/  # 文档存储
        # - base_path/datasets/   # 数据集存储
        # - base_path/chunks/     # 内容寻址块存储
        # - base_path/storage.db  # SQLite 数据库
```

#### Document (document.py)

通用文档存储类：

```python
@dataclass
class Document:
    id: Optional[int]
    name: str
    meta: dict
    ctime: datetime
    mtime: datetime
    atime: datetime
    tags: List[str]
    state: str  # 'ok', 'error', 'warning', 'unknown'
    version: int
    parent_id: Optional[int]  # 版本链
    _data: Optional[dict] = None  # 延迟加载的文档数据
    _chunk_hash: Optional[str] = None
    _script: Optional[str] = None  # 延迟加载的分析代码
    _script_hash: Optional[str] = None
    _storage: Optional[LocalStorage] = None  # 用于延迟加载

    # 数据访问（延迟加载）
    @property
    def data(self) -> dict: ...

    # 代码访问（延迟加载）
    @property
    def script(self) -> Optional[str]: ...
    @property
    def script_hash(self) -> Optional[str]: ...
```

**设计说明：**
- `data`: 文档数据，内容寻址存储，延迟加载
- `script` / `script_hash`: 分析代码，内容寻址存储，延迟加载
- `_storage` 和 `_chunk_hash` 引用用于延迟加载时访问 chunk 存储
- 延迟加载优点：访问文档元数据时不会加载大量数据
- 适合存储生成此文档的分析/处理代码

#### Dataset (datastore.py)

数据集存储类：

```python
class Dataset:
    def __init__(self, id: Optional[int], storage: LocalStorage, name: str = ""):
        self.id = id
        self.storage = storage
        self.name = name
        self._description: Optional[dict] = None
        self._arrays: Dict[str, Array] = {}
        self._config: Optional[dict] = None  # 延迟加载的配置
        self._config_hash: Optional[str] = None
        self._script: Optional[str] = None  # 延迟加载的代码
        self._script_hash: Optional[str] = None

    # 数组操作
    def keys(self) -> List[str]: ...
    def get_array(self, key: str) -> Array: ...
    def create_array(self, key: str, inner_shape: tuple) -> Array: ...
    def append(self, position: tuple, data: dict) -> None: ...
    def flush(self) -> None: ...

    # 配置访问（延迟加载）
    @property
    def config(self) -> Optional[dict]: ...
    @property
    def config_hash(self) -> Optional[str]: ...

    # 代码访问（延迟加载）
    @property
    def script(self) -> Optional[str]: ...
    @property
    def script_hash(self) -> Optional[str]: ...
```

**设计说明：**
- `config` / `config_hash`: 实验配置参数，内容寻址存储，延迟加载
- `script` / `script_hash`: 数据采集代码，内容寻址存储，延迟加载
- 哈希值存储在数据库中，实际内容存储在 chunk 文件

#### Array (array.py)

多维数组存储类：

```python
class Array:
    BUFFER_SIZE = 1000  # 内存缓冲区大小

    def __init__(self, name: str, storage: LocalStorage, dataset_id: int, ...):
        self.name = name
        self.storage = storage
        self.dataset_id = dataset_id
        self._buffer: List[Tuple[Tuple, Any]] = []
        self._lock = Lock()
        self.lu: tuple = ()  # 左下边界
        self.rd: tuple = ()  # 右上边界
        self.inner_shape: tuple = ()

    def append(self, pos: tuple, value: Any, dims: Optional[tuple] = None): ...
    def flush(self) -> None: ...
    def iter(self) -> Iterator[Tuple[Tuple, Any]]: ...
    def toarray(self) -> np.ndarray: ...
    def __getitem__(self, slice_tuple): ...
```

### 数据模型

#### Config 模型

配置数据使用内容寻址存储，相同配置只存储一次：

```sql
CREATE TABLE configs (
    id INTEGER PRIMARY KEY,
    config_hash VARCHAR(40) UNIQUE INDEX,  -- SHA1 hash
    size INTEGER,
    ref_count INTEGER DEFAULT 0,  -- 引用计数
    ctime DATETIME DEFAULT CURRENT_TIMESTAMP,
    atime DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**设计说明：**
- `config_hash`: 配置的 SHA1 哈希，用于内容寻址
- `ref_count`: 引用计数，跟踪有多少 Dataset 引用此配置
- 配置内容存储在 `chunks/` 目录下，使用 lzma 压缩的 JSON 格式
- 延迟加载：配置内容按需从 chunk 文件加载

#### Script 模型

代码脚本同样使用内容寻址存储：

```sql
CREATE TABLE scripts (
    id INTEGER PRIMARY KEY,
    script_hash VARCHAR(40) UNIQUE INDEX,  -- SHA1 hash
    size INTEGER,
    language VARCHAR DEFAULT 'python',  -- python, javascript, etc.
    ref_count INTEGER DEFAULT 0,  -- 引用计数
    ctime DATETIME DEFAULT CURRENT_TIMESTAMP,
    atime DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**设计说明：**
- `script_hash`: 代码的 SHA1 哈希，用于内容寻址
- `language`: 编程语言标识，支持多语言脚本
- `ref_count`: 引用计数，跟踪有多少 Dataset/Document 引用此脚本
- 脚本内容存储在 `chunks/` 目录下，使用 lzma 压缩的文本格式

#### Document 模型

```sql
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    name VARCHAR INDEX,
    state VARCHAR DEFAULT 'unknown',
    version INTEGER DEFAULT 1,
    parent_id INTEGER REFERENCES documents(id),
    chunk_hash VARCHAR(40) INDEX,  -- SHA1 hash (data content)
    chunk_size INTEGER,
    script_id INTEGER REFERENCES scripts(id),  -- 关联的分析代码
    meta JSON DEFAULT '{}',
    ctime DATETIME DEFAULT CURRENT_TIMESTAMP,
    mtime DATETIME DEFAULT CURRENT_TIMESTAMP,
    atime DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 复合索引：优化"查找给定 name 的最新 Document"查询
CREATE INDEX ix_documents_name_ctime ON documents(name, ctime);

CREATE TABLE document_tags (
    item_id INTEGER REFERENCES documents(id),
    tag_id INTEGER REFERENCES tags(id),
    PRIMARY KEY (item_id, tag_id)
);
```

**更新说明：**
- 新增 `script_id` 字段，关联 Script 模型，用于存储生成此文档的分析代码
- 新增复合索引 `ix_documents_name_ctime`，优化"查找给定 name 的最新 Document"查询性能
- 查询默认按 `ctime DESC` 排序，返回最新的文档优先

#### Dataset 模型

```sql
CREATE TABLE datasets (
    id INTEGER PRIMARY KEY,
    name VARCHAR INDEX,
    description JSON,
    config_id INTEGER REFERENCES configs(id),  -- 关联的配置
    script_id INTEGER REFERENCES scripts(id),  -- 关联的采集代码
    ctime DATETIME DEFAULT CURRENT_TIMESTAMP,
    mtime DATETIME DEFAULT CURRENT_TIMESTAMP,
    atime DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 复合索引：优化"查找给定 name 的最新 Dataset"查询
CREATE INDEX ix_datasets_name_ctime ON datasets(name, ctime);

CREATE TABLE arrays (
    id INTEGER PRIMARY KEY,
    dataset_id INTEGER REFERENCES datasets(id),
    name VARCHAR NOT NULL,
    file_path VARCHAR NOT NULL,
    inner_shape JSON,
    lu JSON,  -- 左下边界
    rd JSON   -- 右上边界
);
```

**更新说明：**
- 新增 `config_id` 字段，关联 Config 模型，用于存储实验配置参数
- 新增 `script_id` 字段，关联 Script 模型，用于存储数据采集代码
- 新增复合索引 `ix_datasets_name_ctime`，与 Document 保持一致，优化查询性能
- 查询默认按 `ctime DESC` 排序，返回最新的数据集优先

### 内容寻址存储

数据使用 SHA1 哈希进行内容寻址存储：

```
chunks/
├── aa/
│   └── bb/
│       └── aabbccdd...  (完整哈希作为文件名)
├── cc/
│   └── dd/
│       └── ccddeeff...  (完整哈希作为文件名)
```

#### Config 存储格式

配置数据存储为 **lzma 压缩的 JSON**：

```python
# 存储流程
config_dict -> JSON -> bytes -> lzma.compress() -> chunk

# 读取流程
chunk -> lzma.decompress() -> bytes -> JSON -> config_dict

# 示例
config = {"freq": 5e9, "power": -10, "nested": {"a": 1}}
config_bytes = lzma.compress(json.dumps(config, sort_keys=True).encode())
config_hash = sha1(config_bytes).hexdigest()  # 用于寻址
```

**设计理由：**
- `sort_keys=True` 确保相同配置字典产生相同的 JSON，实现去重
- lzma 压缩减少存储空间，配置数据通常有高压缩率
- SHA1 基于压缩后的数据计算，确保内容寻址准确性

#### Script 存储格式

脚本代码存储为 **lzma 压缩的文本**：

```python
# 存储流程
code -> bytes -> lzma.compress() -> chunk

# 读取流程
chunk -> lzma.decompress() -> bytes -> code

# 示例
code = "import numpy as np\nprint(np.sin(0.5))"
script_bytes = lzma.compress(code.encode('utf-8'))
script_hash = sha1(script_bytes).hexdigest()  # 用于寻址
```

#### 引用计数管理

Config 和 Script 使用引用计数跟踪使用情况：

```python
# 创建 Dataset 时递增引用计数
config.ref_count += 1
script.ref_count += 1

# 删除 Dataset 时递减引用计数
config.ref_count -= 1
script.ref_count -= 1

# 当 ref_count 为 0 时，可以考虑清理 chunk 文件（可选）
```

优势：
- 自动去重：相同内容只存储一次
- 数据完整性验证：SHA1 哈希验证
- 支持大文件分块：通过 chunk 机制
- 引用追踪：通过 ref_count 管理生命周期

## 远程访问

### ZMQ 协议

使用 ZMQ ROUTER/DEALER 模式实现异步 RPC：

**请求格式：**
```python
{
    "method": "document_create",
    "name": "...",
    "data": {...},
    "state": "...",
    "tags": [...],
    "meta": {...}
}
```

**响应格式：**
```python
{
    "result": ...  # 或 {"error": "..."}
}
```

### API 列表

- `document.create` - 创建文档（支持 script 参数）
- `document.get` - 获取文档
- `document.get_latest` - 获取指定名称的最新文档
- `document.query` - 查询文档
- `document.count` - 计数文档
- `document.delete` - 删除文档
- `dataset.create` - 创建数据集（支持 config 和 script 参数）
- `dataset.get` - 获取数据集
- `dataset.query` - 查询数据集
- `dataset.count` - 计数数据集
- `dataset.append` - 追加数据
- `dataset.delete` - 删除数据集
- `array.getitem` - 获取数组元素
- `array.iter` - 迭代数组
- `config.load` - 加载配置（内容寻址）
- `script.load` - 加载代码（内容寻址）

## 配置

```ini
# qulab.ini
[storage]
data = ~/.qulab/storage          # 默认存储路径
server_port = 6789               # 默认服务器端口

[storage.server]
host = 127.0.0.1
port = 6789
```

## 与旧版本兼容

新存储系统不保证与现有 API 完全向后兼容。原有模块保持不变：

- `qulab.executor.storage` - 继续使用
- `qulab.scan.record` - 继续使用
- `qulab.storage` - 新统一存储

迁移路径：
1. 逐步将新代码迁移到 `qulab.storage`
2. 使用新的 Document/Dataset API
3. 旧模块在未来版本中逐步弃用

## 性能考虑

### 写入优化

- Array 使用内存缓冲区 (BUFFER_SIZE=1000)
- 批量写入减少磁盘 I/O
- 内容寻址自动去重

### 读取优化

- 数据库索引支持快速查询
- 复合索引 `ix_documents_name_ctime` 和 `ix_datasets_name_ctime` 优化"查找最新"查询
- 惰性加载数组数据
- 惰性加载文档数据 (`Document.data`)
- 支持切片操作避免全量加载

### 查询优化

**最常用的查询模式 - 获取最新文档：**

```python
# 获取指定名称的最新文档（使用复合索引优化）
latest = storage.get_latest_document(name="calibration")

# 等效的 SQL 查询（使用复合索引 ix_documents_name_ctime）
SELECT * FROM documents
WHERE name = 'calibration'
ORDER BY ctime DESC
LIMIT 1;
```

**复合索引设计：**
- `ix_documents_name_ctime(name, ctime)`: 优化 Document 的"按名称查找最新"查询
- `ix_datasets_name_ctime(name, ctime)`: 优化 Dataset 的"按名称查找最新"查询
- 两个查询都默认按 `ctime DESC` 排序，返回最新的记录优先

### 存储优化

- lzma 压缩减少存储空间
- 内容寻址避免重复数据
- 文件分片支持大文件
- **配置/代码去重**：相同配置和代码只存储一次，通过引用计数管理生命周期

### 配置与代码管理优化

**去重效率：**
- 配置使用 SHA1(lzma(JSON)) 作为哈希，确保相同配置产生相同哈希
- 代码使用 SHA1(lzma(code)) 作为哈希，确保相同代码产生相同哈希
- 引用计数跟踪使用情况，支持清理未引用的 chunk

**延迟加载：**
- 文档数据 (`data`)、配置 (`config`) 和代码 (`script`) 按需加载，减少内存占用
- 数据库只存储哈希值，查询效率高
- 适合存储大型数据、配置和代码文件
- 访问文档元数据（如 `name`, `tags`, `state`）时不会触发数据加载

## 安全考虑

1. **数据完整性** - SHA1 哈希验证
2. **访问控制** - 通过文件系统权限
3. **远程安全** - ZMQ CURVE 加密支持

## 未来扩展

1. **分布式存储** - 支持多节点存储集群
2. **缓存层** - Redis/Memcached 缓存支持
3. **压缩算法** - 支持多种压缩算法 (lz4, zstd)
4. **数据迁移** - 自动数据迁移工具
5. **备份恢复** - 增量备份支持
