QuLab Trace - Jupyter Notebook 行为追踪
========================================

``qulab.trace`` 模块记录用户在 Jupyter Notebook 中的操作行为（代码执行、输出查看、
图像查看、参数修改、markdown 编辑），将行为轨迹上传到服务器，用于训练自动化数据采集
和分析的 AI 模型。

.. contents:: 目录
   :local:

快速开始
--------

客户端（Notebook 中）
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import qulab.trace
   qulab.trace.enable()
   # 之后所有 cell 执行自动被记录
   # 同时监听 notebook 文件保存，捕获 markdown 和结构变更

   # 停止记录
   qulab.trace.disable()

服务端
~~~~~~

.. code-block:: bash

   qulab trace serve --host 0.0.0.0 --port 8790

架构概览
--------

::

   ┌─────────────────────────┐    HTTP POST     ┌─────────────────────┐
   │    Jupyter Notebook      │ ───────────────> │    Trace Server      │
   │                         │  /api/v1/events  │                     │
   │  IPython Hooks          │                  │  FastAPI + Uvicorn  │
   │  ├─ pre_run_cell        │   ┌──────────┐   │  ├─ JSONL storage   │
   │  │  (DisplayCapture)    │   │ 本地缓冲  │   │  └─ SQLite index    │
   │  └─ post_run_cell       │   │ JSONL文件  │   │                     │
   │                         │   └──────────┘   │  TraceStore          │
   │  Notebook Watcher       │                  └─────────────────────┘
   │  └─ watchdog on .ipynb  │
   │                         │
   │  TraceClient            │
   └─────────────────────────┘

捕获机制
--------

**双通道捕获**：

1. **IPython 钩子** — 实时捕获代码执行：

   - ``pre_run_cell``: 记录代码、cell_id、与上次执行的 diff；安装 ``DisplayCapture``
     拦截 inline figure 渲染
   - ``post_run_cell``: 记录执行结果、stdout/stderr、display 输出（包括 matplotlib
     inline 图像）、异常信息

2. **Notebook 文件 Watcher** — 捕获 notebook 结构变更：

   - 使用 ``watchdog`` 监听 ``.ipynb`` 文件保存事件
   - 记录所有 cell（包括 markdown）的内容和顺序
   - 检测 cell 的增删改

**图像捕获原理**：

matplotlib inline backend 在 ``post_execute`` 事件中调用 ``plt.close('all')``，
这发生在 ``post_run_cell`` **之前**。因此直接调用 ``plt.get_fignums()`` 会得到空列表。

解决方案：在 ``pre_run_cell`` 中替换 IPython 的 ``display_pub`` 为 ``DisplayCapture``
包装器，拦截所有 ``display()`` 调用（包括 inline figure 的渲染），在 ``post_run_cell``
中恢复原始 publisher 并读取捕获的输出。图像数据已是 base64 PNG 格式。

事件类型
--------

+-----------------------+---------------------------------------------------+
| 事件类型              | 说明                                              |
+=======================+===================================================+
| ``session_start``     | Kernel 启动，记录 Python 版本、主机名、notebook 路径 |
+-----------------------+---------------------------------------------------+
| ``session_end``       | 追踪关闭，记录总事件数                            |
+-----------------------+---------------------------------------------------+
| ``cell_execute_start``| Cell 开始执行，包含 cell_id、代码全文、diff       |
+-----------------------+---------------------------------------------------+
| ``cell_execute_end``  | Cell 执行完毕，包含耗时、成功/失败、MIME 类型      |
+-----------------------+---------------------------------------------------+
| ``cell_output``       | Cell 文本输出、stdout/stderr                       |
+-----------------------+---------------------------------------------------+
| ``cell_error``        | Cell 异常，ename/evalue/traceback                  |
+-----------------------+---------------------------------------------------+
| ``display_data``      | Display 输出：图像、HTML、富文本（含 inline 图像）  |
+-----------------------+---------------------------------------------------+
| ``notebook_save``     | Notebook 保存，含全部 cell 快照和变更 diff         |
+-----------------------+---------------------------------------------------+

所有执行相关事件包含 ``cell_id`` 字段（来自 Jupyter protocol 5.5+ 的 cell UUID），
可直接对应 ``.ipynb`` 文件中的 cell。

配置
----

通过环境变量配置：

- ``QULAB_TRACE_URL``: 服务器完整 URL（优先）
- ``QULAB_TRACE_HOST``: 服务器地址（默认 ``127.0.0.1``）
- ``QULAB_TRACE_PORT``: 服务器端口（默认 ``8790``）
- ``QULAB_TRACE_USER_ID``: 用户标识

嵌入其他框架
~~~~~~~~~~~~

.. code-block:: python

   from qulab.trace import TraceClient, setup_trace_hooks
   from qulab.trace.watcher import NotebookWatcher

   client = TraceClient(server_url="http://server:8790")
   client.start()
   setup_trace_hooks(client)

   # 可选：监听 notebook 文件变更
   watcher = NotebookWatcher(client, "path/to/notebook.ipynb")
   watcher.start()

   # ... 框架代码 ...

   watcher.stop()
   client.stop()

服务端 API
----------

+-------------------------------+------+-------------------------------------+
| 端点                          | 方法 | 说明                                |
+===============================+======+=====================================+
| ``/api/v1/events``            | POST | 批量接收事件                        |
+-------------------------------+------+-------------------------------------+
| ``/api/v1/sessions``          | GET  | 查询 session 列表                   |
+-------------------------------+------+-------------------------------------+
| ``/api/v1/sessions/{id}/events``| GET| 查询某 session 的事件序列           |
+-------------------------------+------+-------------------------------------+
| ``/api/v1/export``            | GET  | 导出训练数据（JSONL 流式响应）      |
+-------------------------------+------+-------------------------------------+
| ``/api/v1/status``            | GET  | 服务状态/统计信息                   |
+-------------------------------+------+-------------------------------------+

CLI 命令
--------

.. code-block:: bash

   # 启动服务
   qulab trace serve [--host HOST] [--port PORT] [--data-path PATH]

   # 导出训练数据
   qulab trace export [--output FILE] [--session-id ID] [--after DATE] [--before DATE]

   # 查看服务状态
   qulab trace status [--host HOST] [--port PORT]

   # 上传本地缓冲（服务器恢复后补传）
   qulab trace upload-buffer [--buffer-dir DIR] [--server-url URL]

训练数据格式
------------

导出的 JSONL 每行是一个完整 session trace，记录完整的「运行 → 观察 → 修改参数 →
重新运行」行为循环：

.. code-block:: json

   {
     "session_id": "abc123",
     "notebook_path": "Simulate/T1_measurement.ipynb",
     "events": [
       {"seq": 1, "type": "cell_execute_start",
        "cell_id": "a1b2c3", "code": "scan = Scan(...)"},
       {"seq": 2, "type": "cell_execute_end",
        "duration_ms": 30200, "success": true},
       {"seq": 3, "type": "display_data",
        "mime_bundle": {"image/png": "iVBOR...", "text/plain": "<Figure>"}},
       {"seq": 4, "type": "cell_execute_start",
        "cell_id": "a1b2c3", "code": "scan = Scan(...)",
        "diff_ops": [{"op": "delete", "line": "f=4.5e9"},
                     {"op": "insert", "line": "f=5.0e9"}]},
       {"seq": 5, "type": "notebook_save",
        "cells": [{"id": "a1b2c3", "cell_type": "code", ...},
                  {"id": "d4e5f6", "cell_type": "markdown", ...}],
        "changed_cells": [{"id": "a1b2c3", "change": "modified"}]}
     ]
   }
