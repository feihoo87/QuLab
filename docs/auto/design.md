# qulab.auto 设计文档

## 概述

`qulab.auto` 是 QuLab 的自动实验运行框架，仿照 nanobot 设计，使用 LLM 作为决策中心来协调量子实验的自动化执行。

## 设计目标

1. **LLM 驱动决策** - 使用大语言模型作为决策中心，理解实验目标并协调执行
2. **可配置 LLM 提供商** - 支持多种 LLM（Anthropic Claude, OpenAI, Kimi 等）
3. **规则驱动** - 通过 Skill 文件描述实验和分析方法
4. **数据持久化** - 测量任务产生 Dataset，分析任务产生 Document
5. **人机协作** - 支持询问人类并处理人类反馈
6. **会话持久化** - 完整记录决策过程，支持断点续传

## 核心概念

### 架构组件

| 组件 | 职责 | 对应模块 |
|------|------|----------|
| **Agent** | ReAct 决策循环，协调 LLM 和工具执行 | `agent.loop` |
| **LLM Provider** | 大语言模型接口封装 | `llm.*` |
| **Skill** | 实验/分析方法定义 | `skills.*` |
| **Tool** | 具体执行工具 | `tools.*` |
| **Memory** | 会话历史持久化 | `agent.memory` |

### 数据流

```
用户指令 → Agent → LLM 决策 → 工具执行 → 生成 Dataset/Document → LLM 评估 → ...
                ↑                                              ↓
                └──────────── 人类反馈（如需要）←─────────────┘
```

### Skill 类型

1. **Measurement Skill** - 测量任务
   - 输入：测量参数
   - 输出：Dataset + 提取的参数
   - 示例：qubit 能谱扫描

2. **Analysis Skill** - 分析任务
   - 输入：Dataset IDs + 分析参数
   - 输出：Document（含提取的信息）
   - 示例：洛伦兹拟合

## 架构设计

### 模块结构

```
qulab/auto/
├── __init__.py              # 公共 API 导出
├── main.py                  # AutoLab 主类
├── config.py                # 配置管理 (LLMConfig, AutoLabConfig)
├── exceptions.py            # 异常定义
├── cli.py                   # 命令行接口
├── agent/                   # 决策中心
│   ├── __init__.py
│   ├── loop.py              # ReAct 决策循环
│   └── memory.py            # 会话记忆管理
├── llm/                     # LLM 提供商
│   ├── __init__.py
│   ├── base.py              # LLM 抽象基类
│   ├── openai.py            # OpenAI 兼容 API
│   ├── anthropic.py         # Anthropic Claude
│   └── registry.py          # 提供商注册表
├── skills/                  # 技能系统
│   ├── __init__.py
│   ├── base.py              # Skill 基类
│   ├── loader.py            # Skill 加载器
│   └── builtin/             # 内置技能
├── tools/                   # 工具系统
│   ├── __init__.py
│   ├── base.py              # Tool 基类
│   ├── registry.py          # 工具注册表
│   ├── query.py             # 查询工具
│   ├── measurement.py       # 测量工具
│   ├── analysis.py          # 分析工具
│   ├── config.py            # 配置更新工具
│   └── human.py             # 询问人类工具
└── models/                  # 数据模型
    ├── __init__.py
    └── session.py           # 会话状态模型
```

### 核心类设计

#### AutoLab (main.py)

主入口类，整合所有组件：

```python
class AutoLab:
    def __init__(self, storage, llm_config, skills_path, config):
        self.storage = storage          # 存储实例
        self.llm_provider = ...         # LLM 提供商
        self.skill_loader = ...         # 技能加载器
        self.tools = ...                # 工具注册表
        self.memory = ...               # 会话记忆
        self.agent = ...                # 决策循环

    async def start(self, instruction) -> AsyncIterator[AgentEvent]:
        """启动实验会话"""

    async def respond(self, response) -> AsyncIterator[AgentEvent]:
        """响应人类输入"""
```

#### AgentLoop (agent/loop.py)

实现 ReAct (Reasoning + Acting) 模式：

```python
class AgentLoop:
    async def run(self, initial_message) -> AsyncIterator[AgentEvent]:
        for iteration in range(max_iterations):
            # 1. 构建上下文
            context = self._build_context(messages)

            # 2. 调用 LLM
            response = await self.llm.chat(context, tools)

            # 3. 处理响应
            if not response.tool_calls:
                yield AgentEvent(type="complete", content=...)
                break

            # 4. 执行工具
            for tool_call in response.tool_calls:
                result = await self.tools.execute(tool_call.name, ...)
                yield AgentEvent(type="tool_result", ...)
```

#### Skill (skills/base.py)

技能定义数据结构：

```python
@dataclass
class Skill:
    name: str
    type: str                      # "measurement" 或 "analysis"
    description: str
    capabilities: dict             # 能力描述
    inputs: list[dict]            # 输入参数定义
    outputs: list[dict]           # 输出参数定义
    metadata: dict
    code: str                      # 执行代码

    def to_prompt(self) -> str:    # 转换为 LLM prompt
    def validate_inputs(self, ...) -> list[str]:
```

#### BaseTool (tools/base.py)

工具基类：

```python
class BaseTool(ABC):
    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult: ...

    def to_definition(self) -> dict:   # OpenAI function format
    def validate_args(self, ...) -> list[str]:
```

### LLM 提供商设计

#### 抽象基类 (llm/base.py)

```python
class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages, tools, tool_choice) -> LLMResponse: ...

@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall]
    model: str
    usage: dict | None
```

#### 提供商实现

1. **OpenAIProvider** - 支持 OpenAI 兼容 API（Kimi, OpenAI 等）
2. **AnthropicProvider** - 支持 Claude API

### Skill 文件格式

采用 YAML frontmatter + Markdown 格式：

```yaml
---
name: skill_name
type: measurement
description: |
  技能描述

capabilities:
  排查问题:
    - 问题1: 解决方案
  校准参数:
    - 参数1: 描述

inputs:
  - name: param1
    type: string
    description: 参数描述
    default: 默认值

outputs:
  - name: result1
    type: number
    description: 结果描述

metadata:
  tags: [tag1, tag2]
  estimated_time: 60
---

```python
def run(param1, ctx=None):
    # 执行代码
    return {
        'dataset': {...},      # 测量技能必须返回
        'result1': value,
    }
```
```

### 工具系统

| 工具 | 用途 | 关键参数 |
|------|------|----------|
| `query_storage` | 查询 Datasets 和 Documents | type, name, tags, state |
| `run_measurement` | 执行测量技能 | skill, parameters, tags |
| `run_analysis` | 执行分析技能 | skill, parameters, dataset_ids |
| `update_config` | 请求配置更新 | updates, reason |
| `ask_human` | 询问人类 | question, options |

### 会话记忆

使用 JSONL 格式持久化：

```jsonl
{"timestamp": "2024-01-01T00:00:00", "type": "session_start", "session_id": "..."}
{"timestamp": "2024-01-01T00:00:01", "type": "message", "data": {"role": "user", "content": "..."}}
{"timestamp": "2024-01-01T00:00:02", "type": "message", "data": {"role": "assistant", "tool_calls": [...]}}
{"timestamp": "2024-01-01T00:00:03", "type": "tool_execution", "tool_name": "...", "result": {...}}
```

## 工作流程

### 1. 初始化

```python
storage = LocalStorage("./data")
lab = AutoLab(storage, llm_config={
    "provider": "openai",
    "base_url": "https://api.moonshot.cn/v1",
    "api_key": "sk-...",
    "model": "kimi-k2.5"
})
```

### 2. 启动会话

```python
async for event in lab.start("校准 qubit1 的频率"):
    if event.type == "thinking":
        print(f"思考: {event.content}")
    elif event.type == "tool_call":
        print(f"执行: {event.tool_name}")
    elif event.type == "human_query":
        response = await get_human_response(event.question)
        async for e in lab.respond(response):
            process(e)
```

### 3. 决策流程

1. **评估状态** - 查询已有数据
2. **制定计划** - LLM 决定下一步行动
3. **执行工具** - 调用测量/分析工具
4. **处理结果** - 评估是否需要继续
5. **人类交互** - 必要时询问人类

## 扩展机制

### 添加新 LLM 提供商

```python
class MyProvider(LLMProvider):
    async def chat(self, messages, tools, tool_choice):
        # 实现 API 调用
        return LLMResponse(...)

# 注册
from qulab.auto.llm import ProviderRegistry
registry = ProviderRegistry()
registry.register("my_provider", MyProvider)
```

### 添加新工具

```python
class MyTool(BaseTool):
    name = "my_tool"
    description = "..."
    parameters = {...}

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(data={...})

# 注册到 ToolRegistry
registry.register(MyTool())
```

## 配置

### 配置文件格式 (YAML)

```yaml
llm:
  provider: openai
  base_url: https://api.moonshot.cn/v1
  api_key: ${KIMI_API_KEY}
  model: kimi-k2.5
  temperature: 0.7
  max_tokens: 4096

skills_paths:
  - ./my_skills

max_iterations: 40
enable_thinking: true
auto_approve_configs: false
```

## 与 qulab.storage 集成

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  AutoLab    │────▶│   Agent     │────▶│    LLM      │
│             │     │   Loop      │     │  Provider   │
└──────┬──────┘     └──────┬──────┘     └─────────────┘
       │                   │
       │            ┌──────┴──────┐
       │            │   Tools     │
       │            │  ┌───────┐  │
       └───────────▶│  │ query │  │
                    │  │ meas  │  │
       ┌───────────▶│  │ anal  │  │
       │            │  └───────┘  │
       │            └──────┬──────┘
       │                   │
┌──────┴──────┐     ┌──────┴──────┐
│  Session    │     │  qulab      │
│  Memory     │     │  storage    │
│  (JSONL)    │     │  (Dataset/  │
│             │     │   Document) │
└─────────────┘     └─────────────┘
```
