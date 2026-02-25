# QuLab Auto - 自动实验框架

仿照 nanobot 的自动实验运行框架，用于自动化量子实验流程。

## 特性

- **可配置 LLM**: 支持多种 LLM 提供商（Anthropic, OpenAI 兼容 API 如 Kimi 等）
- **规则驱动**: 通过 Skill 文件描述实验和分析方法
- **数据持久化**: 测量任务产生 Dataset，分析任务产生 Document
- **人机协作**: 支持询问人类并处理人类反馈
- **会话持久化**: 完整记录决策过程

## 快速开始

```python
from qulab.auto import AutoLab
from qulab.storage import LocalStorage

# 初始化存储
storage = LocalStorage("./experiment_data")

# 初始化 AutoLab（使用 Kimi）
lab = AutoLab(storage, llm_config={
    "provider": "openai",
    "base_url": "https://api.moonshot.cn/v1",
    "api_key": "sk-...",
    "model": "kimi-k2.5"
})

# 启动实验会话
async for event in lab.start("校准 qubit1 的频率"):
    print(f"[{event.type}] {event.content}")

    # 如果需要人类响应
    if event.type == "human_query":
        response = input(f"AI 询问: {event.question}\n你的回答: ")
        async for resp_event in lab.respond(response):
            print(f"[{resp_event.type}] {resp_event.content}")
```

## 架构

```
qulab/auto/
├── agent/          # 决策中心
│   ├── loop.py     # ReAct 决策循环
│   └── memory.py   # 会话记忆管理
├── llm/            # LLM 提供商
│   ├── base.py     # 抽象基类
│   ├── openai.py   # OpenAI 兼容 API
│   └── anthropic.py # Claude
├── skills/         # 技能系统
│   ├── base.py     # Skill 基类
│   └── loader.py   # Skill 加载器
└── tools/          # 工具系统
    ├── query.py    # 查询工具
    ├── measurement.py # 测量工具
    └── analysis.py # 分析工具
```

## Skill 文件格式

Skill 文件采用 YAML frontmatter + Markdown 格式：

```yaml
---
name: qubit_spectroscopy
type: measurement
description: 执行量子比特能谱扫描
capabilities:
  排查问题:
    - qubit频率未知: 确定f01频率
inputs:
  - name: qubit_id
    type: string
    description: Qubit标识符
outputs:
  - name: f01
    type: number
    description: qubit频率
metadata:
  tags: [qubit, spectroscopy]
---

```python
def run(qubit_id, ctx=None):
    instrument = ctx.get_instrument(f"{qubit_id}_readout")
    data = instrument.measure()
    return {'dataset': data, 'f01': find_peak(data)}
```
```

## 工具列表

1. **query_storage**: 查询存储中的 Datasets 和 Documents
2. **run_measurement**: 执行测量任务，结果保存为 Dataset
3. **run_analysis**: 执行分析任务，结果保存为 Document
4. **update_config**: 请求更新配置参数
5. **ask_human**: 询问人类

## 配置

配置文件示例 (`autolab.yaml`):

```yaml
llm:
  provider: openai
  base_url: https://api.moonshot.cn/v1
  api_key: ${KIMI_API_KEY}
  model: kimi-k2.5
  temperature: 0.7

skills_paths:
  - ./my_skills

max_iterations: 40
enable_thinking: true
```

## CLI

```bash
# 创建配置模板
qulab auto init-config autolab.yaml

# 列出可用技能
qulab auto list-skills

# 运行实验
qulab auto run --config autolab.yaml "校准 qubit1"

# 列出会话
qulab auto list-sessions
```
