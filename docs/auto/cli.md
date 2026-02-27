# AutoLab CLI 使用指南

AutoLab CLI 提供了命令行界面来运行自动化量子实验。支持单次实验执行和交互式聊天模式。

## 目录

- [快速开始](#快速开始)
- [命令概览](#命令概览)
- [配置管理](#配置管理)
- [运行实验](#运行实验)
- [交互式模式](#交互式模式)
- [查看会话](#查看会话)
- [管理技能](#管理技能)

---

## 快速开始

### 1. 环境配置

设置 API Key（推荐通过环境变量）：

```bash
# 使用 Kimi (推荐)
export KIMI_API_KEY="your-kimi-api-key"

# 或使用 OpenAI
export OPENAI_API_KEY="your-openai-api-key"

# 或使用 Anthropic
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

### 2. 创建配置文件

```bash
qulab auto init-config ./autolab_config.yaml
```

### 3. 运行第一个实验

```bash
qulab auto run "测量 Q1 的能谱"
```

---

## 命令概览

| 命令 | 说明 |
|------|------|
| `qulab auto run` | 运行单次实验 |
| `qulab auto chat` | 启动交互式会话 |
| `qulab auto list-sessions` | 列出所有会话 |
| `qulab auto list-skills` | 列出可用技能 |
| `qulab auto init-config` | 创建示例配置文件 |

---

## 配置管理

### 配置文件优先级

配置按以下顺序加载（后加载的覆盖先加载的）：

1. 默认配置
2. `~/.qulab/config.yaml`
3. `./autolab_config.yaml`
4. `AUTOLAB_CONFIG` 环境变量指定的文件
5. 命令行参数
6. 环境变量 (`KIMI_API_KEY` 等)

### 创建配置文件

```bash
# 创建默认配置文件
qulab auto init-config ./autolab_config.yaml
```

生成的配置文件示例：

```yaml
llm:
  provider: openai
  base_url: https://api.moonshot.cn/v1
  api_key: your-api-key-here
  model: kimi-k2.5
  temperature: 0.7
  max_tokens: 4096

skills_paths:
  - ./skills

max_iterations: 40
enable_thinking: true
```

### 配置项说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `llm.provider` | LLM 提供商 | `openai` |
| `llm.model` | 模型名称 | 必填 |
| `llm.base_url` | API 基础 URL | 可选 |
| `llm.api_key` | API 密钥 | 必填 |
| `llm.temperature` | 采样温度 | `0.7` |
| `llm.max_tokens` | 最大 token 数 | `4096` |
| `llm.timeout` | 请求超时时间 | `120` |
| `skills_paths` | 技能搜索路径 | `[]` |
| `max_iterations` | 最大迭代次数 | `40` |
| `enable_thinking` | 启用思考模式 | `true` |

---

## 运行实验

### 基本用法

```bash
qulab auto run "你的实验指令"
```

### 使用配置文件

```bash
qulab auto run --config ./autolab_config.yaml "测量 Q1 的 Rabi 振荡"
```

### 命令行参数覆盖

```bash
# 指定提供商和模型
qulab auto run \
  --provider openai \
  --model kimi-k2.5 \
  --base-url https://api.moonshot.cn/v1 \
  --api-key $KIMI_API_KEY \
  "测量 Q1 的能谱"

# 指定存储路径
qulab auto run \
  --storage ./my_experiment_data \
  --config ./autolab_config.yaml \
  "分析 T1 数据"
```

### 参数说明

| 参数 | 简写 | 说明 |
|------|------|------|
| `--storage` | `-s` | 数据存储路径 |
| `--config` | `-c` | 配置文件路径 |
| `--provider` | `-p` | LLM 提供商 (`openai`, `anthropic`) |
| `--model` | `-m` | 模型名称 |
| `--base-url` | `-u` | API 基础 URL |
| `--api-key` | `-k` | API 密钥 |

---

## 交互式模式

交互式模式提供聊天界面，可以连续执行多个实验并查看历史记录。

### 启动交互式模式

```bash
# 使用环境变量配置
qulab auto chat

# 使用配置文件
qulab auto chat --config ./autolab_config.yaml

# 指定参数
qulab auto chat --model kimi-k2.5 --storage ./chat_data
```

### 交互式命令

进入交互式模式后，可以使用以下命令：

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/skills` | 列出所有可用技能 |
| `/sessions` | 列出所有会话 |
| `/history <id>` | 查看指定会话的历史 |
| `/load <id>` | 加载会话继续 |
| `/config` | 显示当前配置 |
| `/clear` | 清屏 |
| `/quit`, `/exit` | 退出程序 |

### 使用示例

```
╔══════════════════════════════════════════════════════════════╗
║                    QuLab AutoLab v0.1                        ║
║           Interactive Quantum Experiment System              ║
╚══════════════════════════════════════════════════════════════╝

[AutoLab] > /skills

=== Available Skills ===

[Measurement Skills]
  • qubit_spectroscopy: 测量 Qubit 能谱
  • resonator_spectroscopy: 测量谐振器响应
  • rabi_measurement: 测量 Rabi 振荡

[Analysis Skills]
  • lorentzian_fit: 洛伦兹拟合
  • rabi_fit: Rabi 振荡拟合

[AutoLab] > 测量 Q1 的能谱

[User] 测量 Q1 的能谱
--------------------------------------------------

[Thinking] 我将使用 qubit_spectroscopy 技能来测量 Q1 的能谱...

[Execute] run_measurement
       Args: skill='qubit_spectroscopy', qubit_id='Q1'
[Complete] ✓ Success
       Dataset: 550e8400-e29b-41d4-a716-446655440000...

[Complete] 测量完成，Q1 的共振频率为 5.234 GHz

[Session:550e8400] > /sessions

=== Session List ===
  • 550e8400... | Created: 2026-02-27 10:30:15 | Messages: 3

[Session:550e8400] > /quit
[System] Exiting AutoLab
```

---

## 查看会话

### 列出所有会话

```bash
qulab auto list-sessions --storage ./autolab_data
```

输出示例：

```
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Session ID          ┃ Created At                ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 550e8400...         │ 2026-02-27 10:30:15       │
│ 67890abc...         │ 2026-02-27 09:15:30       │
└─────────────────────┴───────────────────────────┘
```

---

## 管理技能

### 列出可用技能

```bash
# 列出内置技能
qulab auto list-skills

# 指定额外技能路径
qulab auto list-skills --skills-path ./my_skills --skills-path ./custom_skills
```

输出示例：

```
╭─────────────────────────────────────────────────────────────╮
│ Measurement Skills                                           │
╭─────────────────────────────────────────────────────────────╮
│ • qubit_spectroscopy                                         │
│ • resonator_spectroscopy                                     │
│ • rabi_measurement                                           │
│ • t1_measurement                                             │
│ • t2_measurement                                             │
╰─────────────────────────────────────────────────────────────╯
╭─────────────────────────────────────────────────────────────╮
│ Analysis Skills                                              │
╭─────────────────────────────────────────────────────────────╮
│ • lorentzian_fit                                             │
│ • rabi_fit                                                   │
│ • decay_fit                                                  │
╰─────────────────────────────────────────────────────────────╯
```

### 自定义技能路径

可以在配置文件中添加自定义技能路径：

```yaml
skills_paths:
  - ./skills
  - ~/custom_skills
  - /opt/qulab/skills
```

---

## 完整使用示例

### 示例 1：能谱测量与分析

```bash
# 步骤 1：测量能谱
qulab auto run "测量 Q1 的能谱，频率范围 4-6 GHz"

# 步骤 2：分析数据（在交互式模式中）
qulab auto chat
# > 对刚才的能谱数据进行洛伦兹拟合
```

### 示例 2：完整的校准流程

```bash
# 启动交互式会话
qulab auto chat --storage ./calibration_data

# 在会话中执行：
# [AutoLab] > 测量 Q1 的能谱
# [AutoLab] > 根据能谱结果校准 Q1 频率
# [AutoLab] > 测量 Q1 的 Rabi 振荡
# [AutoLab] > 计算 pi 脉冲幅度
```

### 示例 3：批量分析

```bash
# 使用脚本批量运行
for qubit in Q1 Q2 Q3; do
    qulab auto run \
        --storage ./batch_data \
        --config ./autolab_config.yaml \
        "测量 ${qubit} 的 T1 衰减"
done
```

---

## 故障排除

### 常见问题

**1. API Key 错误**

```
[red][Error] API Key not set[/red]
```

解决方案：
- 检查环境变量是否正确设置
- 或在配置文件中设置 `api_key`

**2. 模型不支持**

```
Error: Model not available
```

解决方案：
- 确认模型名称正确
- 检查 API Key 是否有权限访问该模型

**3. 技能未找到**

```
No skills found.
```

解决方案：
- 检查 `skills_paths` 配置
- 确认技能文件存在且格式正确

### 调试模式

查看详细日志：

```bash
# 设置日志级别
export LOGURU_LEVEL=DEBUG
qulab auto run "测量 Q1 能谱"
```

---

## 最佳实践

1. **使用配置文件**：将常用配置保存在 `autolab_config.yaml` 中
2. **分离数据存储**：不同实验使用不同的 `--storage` 路径
3. **保存 API Key**：使用环境变量而非命令行参数
4. **利用交互模式**：复杂实验使用 `chat` 模式便于调试
5. **定期清理**：删除旧的会话和不再需要的数据

---

## 相关文档

- [技能编写指南](./skills.md) - 如何编写自定义技能
- [架构设计](./design.md) - AutoLab 系统架构
- [API 参考](./api.md) - Python API 文档
