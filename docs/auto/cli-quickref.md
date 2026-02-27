# AutoLab CLI 快速参考

## 启动命令

```bash
# 单次实验
qulab auto run "测量 Q1 能谱"

# 交互式模式
qulab auto chat

# 使用配置文件
qulab auto run --config ./config.yaml "指令"
```

## 常用选项

| 选项 | 说明 | 示例 |
|------|------|------|
| `-c, --config` | 配置文件 | `--config ./config.yaml` |
| `-s, --storage` | 存储路径 | `--storage ./data` |
| `-p, --provider` | LLM 提供商 | `--provider openai` |
| `-m, --model` | 模型名称 | `--model kimi-k2.5` |
| `-u, --base-url` | API 地址 | `--base-url https://api.moonshot.cn/v1` |
| `-k, --api-key` | API 密钥 | `--api-key sk-...` |

## 交互式命令

| 命令 | 功能 |
|------|------|
| `/help` | 帮助 |
| `/skills` | 列出技能 |
| `/sessions` | 列出会话 |
| `/history <id>` | 查看历史 |
| `/load <id>` | 加载会话 |
| `/config` | 显示配置 |
| `/quit` | 退出 |

## 环境变量

```bash
export KIMI_API_KEY="sk-..."
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-..."
export AUTOLAB_CONFIG="/path/to/config.yaml"
```

## 配置文件示例

```yaml
llm:
  provider: openai
  model: kimi-k2.5
  base_url: https://api.moonshot.cn/v1
  api_key: ${KIMI_API_KEY}
  temperature: 0.7

skills_paths:
  - ./skills

max_iterations: 40
enable_thinking: true
```

## 典型工作流

```bash
# 1. 创建配置
qulab auto init-config ./autolab_config.yaml

# 2. 查看可用技能
qulab auto list-skills

# 3. 启动交互式会话
qulab auto chat --config ./autolab_config.yaml

# 4. 在会话中执行实验
# > 测量 Q1 能谱
# > 拟合数据
# > /quit

# 5. 查看会话历史
qulab auto list-sessions
```
