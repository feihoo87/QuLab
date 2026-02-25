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

## Storage API 参考

### 在 Skill 中使用 Storage

`ctx.storage` 提供了对 storage 系统的访问，可用于查询和创建数据。

#### Dataset 操作

```python
# 获取已有 dataset
ds = ctx.storage.get_dataset(dataset_id)

# 读取数组数据
freqs = ds.get_array('frequencies')
amps = ds.get_array('amplitudes')

# 读取属性
qubit_id = ds.attrs.get('qubit_id')

# 查询 datasets
results = ctx.storage.query_datasets(
    tags=['qubit_spectroscopy'],
    created_after=datetime(2024, 1, 1),
    limit=10
)
```

#### Document 操作

```python
# 获取已有 document
doc = ctx.storage.get_document(document_id)
data = doc.data
state = doc.state

# 查询 documents
results = ctx.storage.query_documents(
    tags=['calibration', 'qubit_01'],
    state='ok',
    limit=5
)

# 获取最近的成功校准
cal_docs = ctx.storage.query_documents(
    tags=['calibration', 'frequency'],
    state='ok',
    sort_by='created_at',
    sort_order='desc',
    limit=1
)
if cal_docs:
    freq = cal_docs[0].data.get('frequency')
```

### 返回多个 Datasets/Documents

#### 测量技能：返回多个 datasets

```python
def run(qubit_ids: list, ctx=None):
    """测量多个比特。"""
    datasets = []
    summary = {}

    for qubit_id in qubit_ids:
        # 执行测量
        data = measure_qubit(qubit_id)

        datasets.append({
            'frequencies': data['freqs'],
            'amplitudes': data['amps'],
            'qubit_id': qubit_id,
        })
        summary[qubit_id] = {
            'f01': data['peak_freq'],
            'visibility': data['visibility'],
        }

    return {
        'datasets': datasets,  # 复数形式返回列表
        'summary': summary,
    }
```

#### 分析技能：返回多个 documents

```python
def run(dataset_ids: list, ctx=None):
    """生成多个分析报告。"""
    documents = []

    for idx in range(len(dataset_ids)):
        ds = ctx.get_dataset(idx)

        # 数据分析
        result = analyze_data(ds)

        documents.append({
            'data': {
                'frequency': result['f0'],
                'linewidth': result['gamma'],
            },
            'state': 'ok' if result['success'] else 'error',
            'extracted_info': {
                'Q': result['f0'] / result['gamma'],
            },
            'tags': ['fit_result'],
            'type': 'fit',
        })

    return {
        'documents': documents,  # 复数形式返回列表
    }
```

## 状态与数据形态示例

分析技能应返回清晰的 state，帮助 LLM 判断结果质量。

### 成功状态 (state: "ok")

```python
return {
    'data': {
        'frequency': 4.523e9,
        'amplitude': 0.85,
        'linewidth': 2.1e6,
        'fit_quality': 0.98,
    },
    'state': 'ok',
    'extracted_info': {
        'f01': 4.523e9,
        'Q': 2154,
        'coherence_time': 150e-6,
    },
}
```

### 警告状态 (state: "warning")

```python
return {
    'data': {
        'frequency': 4.523e9,
        'amplitude': 0.15,  # 信号较弱
        'linewidth': 5.2e6,  # 线宽较宽
        'fit_quality': 0.72,  # 拟合质量一般
    },
    'state': 'warning',
    'extracted_info': {
        'f01': 4.523e9,
        'Q': 870,
        'warning_reason': 'Signal quality below threshold',
        'suggested_action': 'Increase measurement power or check readout',
    },
}
```

### 错误状态 (state: "error")

#### 情况 1：拟合失败
```python
return {
    'data': {
        'error': 'Peak not found in specified range',
        'max_snr': 0.8,  # 信噪比过低
        'search_range': [4.0e9, 5.0e9],
    },
    'state': 'error',
    'extracted_info': {
        'error_type': 'no_peak_found',
        'suggested_action': 'Expand frequency range or check qubit coupling',
    },
}
```

#### 情况 2：数据异常
```python
return {
    'data': {
        'error': 'Unexpected data shape',
        'expected_shape': (100,),
        'actual_shape': (100, 2),
    },
    'state': 'error',
    'extracted_info': {
        'error_type': 'data_shape_mismatch',
        'suggested_action': 'Check measurement configuration',
    },
}
```

#### 情况 3：仪器错误
```python
return {
    'data': {
        'error': 'Instrument connection timeout',
        'instrument': 'VNA_01',
        'timeout_seconds': 30,
    },
    'state': 'error',
    'extracted_info': {
        'error_type': 'instrument_timeout',
        'suggested_action': 'Check instrument connection and retry',
    },
}
```

### 状态判断流程

分析技能应遵循以下流程确定 state：

```python
def run(dataset_ids: list, ctx=None):
    ds = ctx.get_dataset(0)
    data = ds.get_array('amplitudes')

    # 1. 数据有效性检查
    if len(data) == 0:
        return {
            'data': {'error': 'Empty dataset'},
            'state': 'error',
            'extracted_info': {'error_type': 'no_data'},
        }

    # 2. 执行分析
    result = fit_peak(data)

    # 3. 结果质量评估
    if not result['success']:
        return {
            'data': {'error': result['error_message']},
            'state': 'error',
            'extracted_info': {
                'error_type': 'fit_failed',
                'details': result.get('details'),
            },
        }

    # 4. 质量阈值检查
    if result['snr'] < 3.0:
        return {
            'data': result,
            'state': 'warning',
            'extracted_info': {
                'f01': result['frequency'],
                'warning': 'Low SNR detected',
            },
        }

    # 5. 成功
    return {
        'data': result,
        'state': 'ok',
        'extracted_info': {
            'f01': result['frequency'],
            'Q': result['Q'],
        },
    }
```

## 图片生成与存储

利用 LLM 的多模态能力，分析技能可以生成图片并返回。

### 基础图片生成

```python
def run(dataset_ids: list, ctx=None):
    import matplotlib.pyplot as plt

    ds = ctx.get_dataset(0)
    freqs = ds.get_array('frequencies')
    amps = ds.get_array('amplitudes')

    # 创建图片
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(freqs / 1e9, amps, 'b-', label='Data')
    ax.set_xlabel('Frequency (GHz)')
    ax.set_ylabel('Amplitude')
    ax.set_title('Qubit Spectroscopy')
    ax.legend()
    ax.grid(True)

    # 转换为 base64
    img_base64 = ctx.figure_to_base64(fig, image_format='png', dpi=150)
    plt.close(fig)

    return {
        'data': {
            'image': img_base64,
            'caption': 'Qubit spectroscopy showing clear peak at 4.523 GHz',
            'format': 'png',
        },
        'state': 'ok',
        'extracted_info': {
            'peak_frequency': 4.523e9,
        },
    }
```

### 多子图示例

```python
def run(dataset_ids: list, ctx=None):
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    for idx, ax in enumerate(axes.flat):
        if idx < len(dataset_ids):
            ds = ctx.get_dataset(idx)
            freqs = ds.get_array('frequencies')
            amps = ds.get_array('amplitudes')

            ax.plot(freqs / 1e9, amps)
            ax.set_title(f'Qubit {idx}')
            ax.set_xlabel('Frequency (GHz)')
            ax.set_ylabel('Amplitude')

    plt.tight_layout()

    img_base64 = ctx.figure_to_base64(fig, format='png', dpi=150)
    plt.close(fig)

    return {
        'data': {
            'image': img_base64,
            'caption': f'Comparison of {len(dataset_ids)} qubits',
        },
        'state': 'ok',
        'extracted_info': {},
    }
```

### 使用 create_analysis_figure 辅助函数

```python
def run(dataset_ids: list, ctx=None):
    ds = ctx.get_dataset(0)
    data = {
        'x': ds.get_array('frequencies'),
        'y': ds.get_array('amplitudes'),
        'fit_x': ds.get_array('fit_freqs'),
        'fit_y': ds.get_array('fit_amps'),
    }

    def plot_func(fig, ax, d):
        ax.plot(d['x'] / 1e9, d['y'], 'bo', label='Data', markersize=4)
        ax.plot(d['fit_x'] / 1e9, d['fit_y'], 'r-', label='Fit', linewidth=2)
        ax.legend()
        ax.grid(True, alpha=0.3)

    # 使用辅助函数创建标准化图片文档
    figure_doc = ctx.create_analysis_figure(
        data,
        plot_func,
        figsize=(10, 6),
        image_format='png',
        dpi=150,
        xlabel='Frequency (GHz)',
        ylabel='Transmission (a.u.)',
        title='Lorentzian Fit Result',
        caption='Clean Lorentzian fit with Q ~ 5000',
        extra_tags=['qubit_spectroscopy', 'fit_result'],
    )

    # 可以作为多个 documents 之一返回
    return {
        'documents': [
            figure_doc,
            {
                'data': {'fit_params': {'f0': 4.523e9, 'Q': 5234}},
                'state': 'ok',
                'extracted_info': {'f01': 4.523e9, 'Q': 5234},
                'tags': ['fit_params'],
                'type': 'params',
            },
        ],
    }
```

### 为 LLM 多模态优化

生成图片时应考虑 LLM 的视觉理解能力：

```python
def run(dataset_ids: list, ctx=None):
    import matplotlib.pyplot as plt

    ds = ctx.get_dataset(0)

    fig, ax = plt.subplots(figsize=(10, 6), dpi=100)

    # 1. 清晰的线条和标记
    ax.plot(ds.get_array('frequencies') / 1e9,
            ds.get_array('amplitudes'),
            'b-', linewidth=2, label='Signal')

    # 2. 突出关键特征
    peak_idx = np.argmax(ds.get_array('amplitudes'))
    peak_freq = ds.get_array('frequencies')[peak_idx] / 1e9
    peak_amp = ds.get_array('amplitudes')[peak_idx]

    ax.plot(peak_freq, peak_amp, 'ro', markersize=12, label=f'Peak: {peak_freq:.3f} GHz')

    # 3. 清晰的标签
    ax.set_xlabel('Frequency (GHz)', fontsize=12)
    ax.set_ylabel('Amplitude (a.u.)', fontsize=12)
    ax.set_title('Qubit Spectroscopy Result', fontsize=14)

    # 4. 添加注释
    ax.annotate(f'f01 = {peak_freq:.3f} GHz',
                xy=(peak_freq, peak_amp),
                xytext=(peak_freq + 0.01, peak_amp - 0.1),
                arrowprops=dict(arrowstyle='->', color='red'),
                fontsize=11, color='red')

    ax.legend(loc='best', fontsize=11)
    ax.grid(True, alpha=0.3)

    img_base64 = ctx.figure_to_base64(fig, format='png', dpi=150)
    plt.close(fig)

    return {
        'data': {
            'image': img_base64,
            'caption': f'Qubit spectroscopy with clear peak at {peak_freq:.3f} GHz. '
                       f'Look for the red marker indicating the peak position.',
        },
        'state': 'ok',
        'extracted_info': {'f01': peak_freq * 1e9},
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

7. **图片生成建议**
   - 使用适中的 DPI (150-200) 平衡清晰度和数据大小
   - 始终包含清晰的标题和标签
   - 使用颜色突出关键特征
   - 在 caption 中描述关键信息
   - 关闭图片释放内存 (`plt.close(fig)`)

## 技能搜索路径

框架按以下顺序搜索技能：

1. `~/.qulab/skills/` - 用户自定义技能
2. `./skills/` - 项目本地技能
3. `qulab/auto/skills/builtin/` - 内置技能

后加载的技能会覆盖先加载的同名技能。
