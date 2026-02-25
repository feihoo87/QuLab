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

```python
import numpy as np

def run(param_name: str = 'x', start: float = 0, stop: float = 10,
        num_points: int = 101, ctx=None):
    """基础测量示例"""
    # 生成扫描点
    values = np.linspace(start, stop, num_points)

    # 模拟测量（实际应调用仪器）
    # result = ctx.get_instrument('instrument').measure(values)
    result = np.sin(values) + np.random.randn(num_points) * 0.1

    return {
        'dataset': {
            param_name: values,
            'result': result,
        },
        'max_value': float(np.max(result)),
        'min_value': float(np.min(result)),
    }
```
