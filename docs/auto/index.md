# AutoLab 文档

AutoLab 是 QuLab 的自动化实验框架，使用 LLM 驱动实验执行、数据分析和知识沉淀。

## 文档目录

### 用户指南

- [CLI 使用指南](./cli.md) - 命令行界面完整文档
- [CLI 快速参考](./cli-quickref.md) - 常用命令速查表

### 开发文档

- [架构设计](./design.md) - 系统架构详细设计

## 快速开始

```bash
# 1. 安装 QuLab
pip install qulab

# 2. 设置 API Key
export KIMI_API_KEY="your-api-key"

# 3. 运行第一个实验
qulab auto run "测量 Q1 的能谱"
```

## 核心概念

### Skill（技能）

Skill 是可复用的实验/分析模块，使用 Markdown + YAML 格式定义：

- **测量技能** - 控制硬件执行实验
- **分析技能** - 处理数据提取参数
- **元技能** - 编排其他技能

### 三层 Agent 架构

```
Human
  ↓
Planner Agent    → 理解目标、选择技能、制定计划
  ↓
Executor Agent   → 执行实验、控制硬件、生成数据
  ↓
Analysis Agent   → 分析数据、提取参数、更新模型
  ↓
World Model      ← 实验状态、参数、历史记录
```

### World Model

统一的实验状态管理，包括：

- **参数存储** - 带置信度和过期时间的参数管理
- **状态管理** - 实验和设备状态跟踪
- **历史记录** - 完整审计追踪

## 更多信息

- 源码：`qulab/auto/`
- 内置技能：`qulab/auto/skills/builtin/`
- 问题反馈：GitHub Issues
