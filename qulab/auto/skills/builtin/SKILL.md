---
name: basic_measurement
type: measurement
description: |
  基础测量技能模板，用于演示框架功能。
  执行简单的参数扫描并返回数据。

capabilities:
  排查问题:
    - 仪器连接测试: 验证仪器响应
  提取信息:
    - 扫描结果: 记录扫描数据

inputs:
  - name: param_name
    type: string
    description: 扫描参数名
    default: x
  - name: start
    type: number
    description: 扫描起始值
    default: 0
  - name: stop
    type: number
    description: 扫描终止值
    default: 10
  - name: num_points
    type: integer
    description: 扫描点数
    default: 101

outputs:
  - name: max_value
    type: number
    description: 最大值
  - name: min_value
    type: number
    description: 最小值

metadata:
  tags: [basic, template, demo]
  estimated_time: 10
---

## 单 Dataset 格式（向后兼容）

```python
import numpy as np

def run(param_name: str = 'x', start: float = 0, stop: float = 10,
        num_points: int = 101, ctx=None):
    """基础测量示例 - 单 dataset 格式"""
    # 生成扫描点
    values = np.linspace(start, stop, num_points)

    # 模拟测量（实际应调用仪器）
    # result = ctx.get_instrument('instrument').measure(values)
    result = np.sin(values) + np.random.randn(num_points) * 0.1

    # 使用单数 'dataset' 格式（向后兼容）
    return {
        'dataset': {
            param_name: values,
            'result': result,
        },
        'max_value': float(np.max(result)),
        'min_value': float(np.min(result)),
    }
```

## 多 Datasets 格式

```python
import numpy as np

def run_multi_channel(channels: list, start: float = 0, stop: float = 10,
                      num_points: int = 101, ctx=None):
    """多通道测量示例 - 多 datasets 格式

    Args:
        channels: 通道列表，如 ['ch1', 'ch2', 'ch3']
        start: 扫描起始值
        stop: 扫描终止值
        num_points: 扫描点数
        ctx: 测量上下文

    Returns:
        使用 'datasets'（复数）格式返回多个通道的数据
    """
    values = np.linspace(start, stop, num_points)
    datasets = []
    summary = {}

    for channel in channels:
        # 模拟测量（实际应调用仪器）
        # result = ctx.get_instrument('instrument').measure_channel(channel, values)
        phase = np.random.uniform(0, 2 * np.pi)
        result = np.sin(values + phase) + np.random.randn(num_points) * 0.1

        # 为每个通道创建一个 dataset
        datasets.append({
            'x': values,
            'amplitude': result,
            'channel': channel,
        })

        summary[channel] = {
            'max': float(np.max(result)),
            'min': float(np.min(result)),
            'mean': float(np.mean(result)),
        }

    # 使用 'datasets'（复数）格式返回
    return {
        'datasets': datasets,  # 多个 dataset 的列表
        'summary': summary,
        'channels': channels,
    }
```
