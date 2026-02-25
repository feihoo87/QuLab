# QuLab Auto 实验框架指南

## 概述

本框架用于自动化量子实验，通过 LLM 决策中心协调测量和分析任务。

## 核心概念

### Dataset
测量任务产生的数据存储为 Dataset，包含：
- 原始测量数据（Array）
- 测量参数（description）
- 标签（tags）
- 执行脚本（script）

### Document
分析任务产生的报告存储为 Document，包含：
- 分析结果（data）
- 状态（state: ok/error/warning）
- 提取的信息（meta.extracted_info）
- 关联的 Datasets

### Skill
描述实验或分析方法的规则文件，包括：
- 元数据（输入/输出/能力）
- 执行代码

## 工作流程

1. **评估状态**: 使用 `query_storage` 查询已有数据
2. **选择任务**: 根据目标选择测量或分析技能
3. **执行任务**: 使用 `run_measurement` 或 `run_analysis`
4. **分析结果**: 检查生成的 Dataset/Document
5. **更新配置**: 如果需要，使用 `update_config`
6. **询问人类**: 如果不确定，使用 `ask_human`

## 编写 Skill

### Skill 文件格式

Skill 文件使用 YAML frontmatter + Markdown 格式：

```yaml
---
name: skill_name
type: measurement  # 或 analysis
description: |
  技能描述

capabilities:
  排查问题:
    - 问题1: 解决方案1
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
        'dataset': {...},  # 测量技能必须返回
        'result1': value,
    }
```

### 测量技能

- 必须返回包含 `'dataset'` 键的结果
- 使用 `ctx` 访问实验设备
- 在 metadata 中记录关键参数

```python
def run(qubit_id: str, freq_range: list, ctx=None):
    # 获取仪器
    instrument = ctx.get_instrument(f"{qubit_id}_readout")

    # 执行测量
    freqs = np.linspace(freq_range[0], freq_range[1], freq_range[2])
    data = instrument.sweep(frequencies=freqs)

    # 返回结果
    return {
        'dataset': {
            'frequencies': freqs,
            'amplitudes': data,
        },
        'f01': find_peak(data),
    }
```

### 分析技能

- 输入为 `dataset_ids` 列表
- 返回包含 `'data'` 和 `'extracted_info'` 的结果
- 设置适当的 state（ok/error/warning）

```python
def run(dataset_ids: list, peak_prominence: float = 0.1, ctx=None):
    # 获取数据集
    ds = ctx.get_dataset(0)

    # 执行分析
    freqs = ds.get_array('frequencies')
    amps = ds.get_array('amplitudes')

    # 拟合
    result = fit_data(freqs, amps)

    return {
        'data': {
            'frequency': result['f0'],
            'linewidth': result['gamma'],
        },
        'state': 'ok' if result['success'] else 'error',
        'extracted_info': {
            'frequency': result['f0'],
            'Q': result['f0'] / result['gamma'],
        },
    }
```

## 最佳实践

1. **优先使用已有数据进行分析**
   - 测量前先查询 storage
   - 避免重复测量

2. **测量前检查最近的校准状态**
   - 查询最近的校准文档
   - 评估是否需要重新校准

3. **小范围扫描验证后再扩展**
   - 先用粗略参数验证
   - 确认信号存在后再精细扫描

4. **所有异常都应标记为 error 或 warning 状态**
   - 拟合失败 → error
   - 信号质量差 → warning
   - 记录详细的错误信息

5. **提供清晰的参数说明**
   - 输入参数要有合理的默认值
   - 说明参数单位和有效范围

6. **在 extracted_info 中提取关键信息**
   - 便于后续决策使用
   - 提取的数值要标准化

## 技能搜索路径

框架按以下顺序搜索技能：

1. `~/.qulab/skills/` - 用户自定义技能
2. `./skills/` - 项目本地技能
3. `qulab/auto/skills/builtin/` - 内置技能

后加载的技能会覆盖先加载的同名技能。
