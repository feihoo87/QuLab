# qulab.auto 使用文档

## 快速开始

### 安装依赖

```bash
pip install qulab
```

### 基本用法

```python
import asyncio
from qulab.auto import AutoLab
from qulab.storage import LocalStorage

async def main():
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

asyncio.run(main())
```

## 配置

### 通过代码配置

```python
from qulab.auto import AutoLab, AutoLabConfig, LLMConfig

# 创建 LLM 配置
llm_config = LLMConfig(
    provider="openai",
    model="kimi-k2.5",
    base_url="https://api.moonshot.cn/v1",
    api_key="your-api-key",
    temperature=0.7,
    max_tokens=4096,
)

# 创建完整配置
config = AutoLabConfig(
    llm=llm_config,
    skills_paths=["./my_skills"],
    max_iterations=40,
    enable_thinking=True,
)

# 初始化 AutoLab
lab = AutoLab(storage, config=config)
```

### 通过配置文件

创建 `autolab.yaml`：

```yaml
llm:
  provider: openai
  base_url: https://api.moonshot.cn/v1
  api_key: ${KIMI_API_KEY}  # 支持环境变量
  model: kimi-k2.5
  temperature: 0.7
  max_tokens: 4096

skills_paths:
  - ./my_skills
  - ~/.qulab/skills

max_iterations: 40
enable_thinking: true
```

加载配置：

```python
from qulab.auto import AutoLab, AutoLabConfig

config = AutoLabConfig.from_file("autolab.yaml")
lab = AutoLab(storage, config=config)
```

### LLM 提供商配置

#### Kimi (Moonshot)

```python
llm_config = {
    "provider": "openai",
    "base_url": "https://api.moonshot.cn/v1",
    "api_key": "sk-...",
    "model": "kimi-k2.5",
    "temperature": 0.7,
}
```

#### OpenAI

```python
llm_config = {
    "provider": "openai",
    "api_key": "sk-...",
    "model": "gpt-4",
    "temperature": 0.7,
}
```

#### Anthropic Claude

```python
llm_config = {
    "provider": "anthropic",
    "api_key": "sk-ant-...",
    "model": "claude-3-sonnet-20240229",
    "temperature": 0.7,
}
```

## 技能 (Skills)

### 查看可用技能

```python
# 列出所有技能
skills = lab.list_skills()
print(skills)

# 按类型筛选
measurements = lab.list_skills("measurement")
analyses = lab.list_skills("analysis")

# 获取技能详情
info = lab.get_skill_info("qubit_spectroscopy")
print(info["description"])
print(info["inputs"])
print(info["outputs"])
```

### 编写自定义技能

创建 `my_skills/my_measurement/SKILL.md`：

```yaml
---
name: my_measurement
type: measurement
description: |
  我的自定义测量技能。

capabilities:
  排查问题:
    - 信号问题: 调整参数
  校准参数:
    - optimal_param: 最优参数

inputs:
  - name: param1
    type: number
    description: 参数1
    default: 1.0

outputs:
  - name: result
    type: number
    description: 测量结果

metadata:
  tags: [custom, measurement]
---

```python
def run(param1=1.0, ctx=None):
    # 获取仪器（实际实验时使用）
    # instrument = ctx.get_instrument("my_instrument")
    # data = instrument.measure(param1)

    # 模拟数据
    import numpy as np
    data = np.random.randn(100) + param1

    return {
        'dataset': {
            'x': list(range(100)),
            'y': data.tolist(),
        },
        'result': float(np.mean(data)),
    }
```

使用自定义技能路径：

```python
lab = AutoLab(storage, llm_config=config, skills_path="./my_skills")
```

## 会话管理

### 创建和恢复会话

```python
# 创建新会话
async for event in lab.start("新的实验任务"):
    ...

# 指定会话 ID
async for event in lab.start("实验任务", session_id="exp_2024_001"):
    ...

# 恢复已有会话
async for event in lab.start(None, session_id="exp_2024_001"):
    ...
```

### 查看会话历史

```python
# 获取当前会话的消息历史
history = lab.get_session_history()
for msg in history:
    print(f"{msg['role']}: {msg['content']}")

# 获取完整历史（包含工具执行记录）
full_history = lab.get_full_history()

# 列出所有会话
sessions = lab.list_sessions()
for session in sessions:
    print(f"{session['session_id']}: {session['created_at']}")
```

## 处理事件

### 事件类型

| 事件类型 | 说明 | 处理 |
|----------|------|------|
| `thinking` | LLM 思考过程 | 可选显示 |
| `tool_call` | 开始执行工具 | 显示执行信息 |
| `tool_result` | 工具执行完成 | 显示结果 |
| `complete` | 任务完成 | 显示最终结果 |
| `error` | 发生错误 | 显示错误信息 |
| `human_query` | 需要人类输入 | 获取用户响应 |
| `config_request` | 请求配置更新 | 确认或拒绝 |

### 事件处理示例

```python
async for event in lab.start("测量 qubit 频率"):
    if event.type == "thinking":
        # 显示思考过程（可选）
        print(f"🤔 {event.content}")

    elif event.type == "tool_call":
        # 显示工具调用
        print(f"🛠️  执行 {event.tool_name}({event.tool_args})")

    elif event.type == "tool_result":
        # 显示结果
        if event.result.get("success"):
            print(f"✅ 成功: {event.result.get('data')}")
        else:
            print(f"❌ 失败: {event.result.get('error')}")

    elif event.type == "complete":
        # 任务完成
        print(f"✨ 完成: {event.content}")

    elif event.type == "error":
        # 发生错误
        print(f"💥 错误: {event.content}")

    elif event.type == "human_query":
        # 需要人类输入
        print(f"❓ {event.question}")
        if event.options:
            print(f"选项: {event.options}")
        response = input("你的回答: ")
        async for resp_event in lab.respond(response):
            process(resp_event)

    elif event.type == "config_request":
        # 配置更新请求
        print(f"🔧 配置更新请求: {event.reason}")
        print(f"更新内容: {event.updates}")
        confirm = input("确认更新? (y/n): ")
        if confirm.lower() == 'y':
            async for resp_event in lab.respond({"approved": True, "updates": event.updates}):
                process(resp_event)
        else:
            async for resp_event in lab.respond({"approved": False, "reason": "用户拒绝"}):
                process(resp_event)
```

## 命令行界面

### 创建配置模板

```bash
qulab auto init-config autolab.yaml
```

### 列出可用技能

```bash
qulab auto list-skills

# 指定额外技能路径
qulab auto list-skills -p ./my_skills
```

### 运行实验

```bash
# 使用配置文件
qulab auto run --config autolab.yaml "校准 qubit1"

# 直接指定参数
qulab auto run \
    --provider openai \
    --base-url https://api.moonshot.cn/v1 \
    --api-key sk-... \
    --model kimi-k2.5 \
    "执行能谱扫描"
```

### 查看会话

```bash
# 列出所有会话
qulab auto list-sessions

# 指定存储路径
qulab auto list-sessions --storage ./my_data
```

## 完整示例

### 自动能谱扫描和分析

```python
import asyncio
from qulab.auto import AutoLab
from qulab.storage import LocalStorage

async def main():
    # 初始化
    storage = LocalStorage("./experiment_data")
    lab = AutoLab(storage, llm_config={
        "provider": "openai",
        "base_url": "https://api.moonshot.cn/v1",
        "api_key": "sk-...",
        "model": "kimi-k2.5"
    })

    # 定义事件处理器
    async def handle_events(lab, instruction):
        async for event in lab.start(instruction):
            print(f"\n[{event.type}]")

            if event.type == "thinking":
                print(f"  {event.content}")

            elif event.type == "tool_call":
                print(f"  执行: {event.tool_name}")
                print(f"  参数: {event.tool_args}")

            elif event.type == "tool_result":
                result = event.result
                if result.get("success"):
                    print(f"  ✅ 成功")
                    print(f"  数据: {result.get('data', {})}")
                else:
                    print(f"  ❌ 失败: {result.get('error')}")

            elif event.type == "complete":
                print(f"  ✨ 任务完成!")
                print(f"  结果: {event.content}")
                return True

            elif event.type == "error":
                print(f"  💥 错误: {event.content}")
                return False

            elif event.type == "human_query":
                print(f"  ❓ {event.question}")
                if event.options:
                    for i, opt in enumerate(event.options, 1):
                        print(f"    {i}. {opt}")
                response = input("\n你的回答: ")
                async for e in lab.respond(response):
                    print(f"  [{e.type}] {e.content}")

            elif event.type == "config_request":
                print(f"  🔧 {event.reason}")
                print(f"  更新: {event.updates}")
                confirm = input("\n确认? (y/n): ")
                async for e in lab.respond({
                    "approved": confirm.lower() == 'y',
                    "updates": event.updates if confirm.lower() == 'y' else {}
                }):
                    print(f"  [{e.type}] {e.content}")

    # 运行实验
    success = await handle_events(lab, "测量 qubit1 的能谱并拟合洛伦兹线型")

    if success:
        print("\n✅ 实验完成!")
        # 查看生成的数据
        datasets = list(storage.query_datasets(tags=["auto"]))
        print(f"生成了 {len(datasets)} 个数据集")
    else:
        print("\n❌ 实验失败")

if __name__ == "__main__":
    asyncio.run(main())
```

## 调试和日志

### 启用详细输出

```python
import logging

# 启用调试日志
logging.basicConfig(level=logging.DEBUG)

# 或仅启用 auto 模块的日志
logging.getLogger("qulab.auto").setLevel(logging.DEBUG)
```

### 查看会话文件

会话历史保存在存储目录的 `sessions/` 子目录中：

```bash
# 查看会话列表
ls ./experiment_data/sessions/

# 查看会话内容
cat ./experiment_data/sessions/session_20240101_120000.jsonl
```

## 最佳实践

### 1. 从简单任务开始

```python
# 先测试简单的查询
async for event in lab.start("查看最近的校准数据"):
    ...
```

### 2. 使用环境变量管理 API 密钥

```bash
export KIMI_API_KEY="sk-..."
```

```python
import os

llm_config = {
    "provider": "openai",
    "base_url": "https://api.moonshot.cn/v1",
    "api_key": os.environ["KIMI_API_KEY"],
    "model": "kimi-k2.5",
}
```

### 3. 保存重要会话

```python
# 使用有意义的会话 ID
async for event in lab.start("任务", session_id="exp_qubit1_20240101"):
    ...
```

### 4. 自定义系统提示词

```python
config = AutoLabConfig(
    llm=llm_config,
    custom_system_prompt="""
你是一个量子实验助手。请遵循以下原则：
1. 优先使用已有数据
2. 测量前检查校准状态
3. 详细记录每个步骤
"""
)
```

## 故障排除

### LLM API 错误

```python
# 检查配置
print(lab.llm_provider.name)  # 应显示正确的提供商

# 测试连接
try:
    from qulab.auto.llm import LLMResponse
    response = await lab.llm_provider.chat(
        [{"role": "user", "content": "Hello"}]
    )
    print(response.content)
except Exception as e:
    print(f"连接失败: {e}")
```

### 技能未找到

```python
# 检查技能路径
print(loader.search_paths)

# 重新加载
skills = lab.skill_loader.load_all(force_reload=True)
print(f"加载了 {len(skills)} 个技能")
```

### 会话恢复失败

```python
# 检查会话是否存在
sessions = lab.list_sessions()
session_ids = [s["session_id"] for s in sessions]
print(f"可用会话: {session_ids}")
```
