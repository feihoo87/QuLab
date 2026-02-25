---
name: qubit_spectroscopy
type: measurement
description: |
  执行量子比特单音能谱扫描。通过扫描 probe 频率并测量响应，
  确定 qubit 的基态到第一激发态跃迁频率 (f01)。

capabilities:
  排查问题:
    - qubit频率未知: 确定f01频率
    - qubit频率漂移: 重新校准频率
    - 信号弱: 识别最优驱动功率
  校准参数:
    - f01: qubit跃迁频率 (Hz)
    - drive_power: 驱动功率 (dBm)

inputs:
  - name: qubit_id
    type: string
    description: Qubit标识符
    required: true
  - name: freq_center
    type: number
    description: 扫描中心频率 (Hz)
    default: 5.0e9
  - name: freq_span
    type: number
    description: 扫描频率范围 (Hz)
    default: 200.0e6
  - name: num_points
    type: integer
    description: 扫描点数
    default: 501
  - name: drive_power
    type: number
    description: 驱动功率 (dBm)
    default: -50.0

outputs:
  - name: f01
    type: number
    description: 识别的qubit频率 (Hz)
  - name: fwhm
    type: number
    description: 谱线半高全宽 (Hz)
  - name: snr
    type: number
    description: 信噪比 (dB)

metadata:
  tags: [qubit, spectroscopy, calibration, frequency]
  estimated_time: 60
  author: auto-lab
---

```python
import numpy as np
from scipy.signal import find_peaks

def lorentzian(f, f0, A, gamma, offset):
    """洛伦兹线型函数"""
    return offset + A * gamma**2 / ((f - f0)**2 + gamma**2)

def run(qubit_id: str, freq_center: float = 5.0e9, freq_span: float = 200.0e6,
        num_points: int = 501, drive_power: float = -50.0, ctx=None):
    """执行能谱扫描

    Args:
        qubit_id: Qubit标识符
        freq_center: 扫描中心频率 (Hz)
        freq_span: 扫描频率范围 (Hz)
        num_points: 扫描点数
        drive_power: 驱动功率 (dBm)
        ctx: 测量上下文

    Returns:
        包含测量数据和提取参数的字典（使用单数 dataset 格式）
    """
    # 生成频率轴
    freqs = np.linspace(freq_center - freq_span/2,
                       freq_center + freq_span/2, num_points)

    # 使用ctx获取仪器并执行测量
    # 实际实现中通过ctx访问实验设备
    instrument = ctx.get_instrument(f"{qubit_id}_readout")

    # 执行测量（实际调用）
    # data = instrument.sweep(frequencies=freqs, power=drive_power)

    # 模拟数据用于演示
    # 实际使用时删除此模拟部分
    f01_true = freq_center + 10e6
    gamma = 2e6
    A = 0.1
    offset = 0.5
    noise = 0.01

    data = lorentzian(freqs, f01_true, A, gamma, offset)
    data += np.random.randn(num_points) * noise

    # 峰值检测
    peaks, properties = find_peaks(np.abs(data - offset), prominence=0.01)

    if len(peaks) > 0:
        # 取最显著的峰值
        main_peak_idx = peaks[np.argmax(properties['prominences'])]
        f01 = freqs[main_peak_idx]

        # 计算FWHM（基于峰值高度）
        peak_height = data[main_peak_idx] - offset
        half_max = offset + peak_height / 2

        # 找半高位置
        above_half = data > half_max
        indices = np.where(above_half)[0]
        if len(indices) > 0:
            fwhm = freqs[indices[-1]] - freqs[indices[0]]
        else:
            fwhm = gamma * 2  # 默认值

        # 计算SNR
        signal = np.max(np.abs(data - offset))
        noise_std = np.std(data[:50])  # 假设前50点是噪声
        snr = 20 * np.log10(signal / noise_std) if noise_std > 0 else 0
    else:
        # 未检测到峰值，返回中心频率
        f01 = freq_center
        fwhm = freq_span
        snr = 0

    return {
        'dataset': {
            'frequencies': freqs,
            'amplitudes': data,
        },
        'f01': float(f01),
        'fwhm': float(fwhm),
        'snr': float(snr),
        'metadata': {
            'qubit_id': qubit_id,
            'drive_power': drive_power,
            'peak_detected': len(peaks) > 0,
        }
    }
```

---

## 多Qubit测量示例（返回多个 datasets）

以下示例展示如何使用 `datasets`（复数）格式返回多个qubit的测量结果：

```python
def run_multi_qubit(qubit_ids: list, freq_center: float = 5.0e9,
                    freq_span: float = 200.0e6, num_points: int = 501,
                    drive_power: float = -50.0, ctx=None):
    """测量多个qubit的能谱

    Args:
        qubit_ids: Qubit标识符列表，如 ['Q1', 'Q2', 'Q3']
        freq_center: 扫描中心频率 (Hz)
        freq_span: 扫描频率范围 (Hz)
        num_points: 扫描点数
        drive_power: 驱动功率 (dBm)
        ctx: 测量上下文

    Returns:
        使用 datasets（复数）格式返回多个qubit的测量数据
    """
    datasets = []
    summary = {}

    for qubit_id in qubit_ids:
        # 生成频率轴
        freqs = np.linspace(freq_center - freq_span/2,
                           freq_center + freq_span/2, num_points)

        # 获取仪器并执行测量
        instrument = ctx.get_instrument(f"{qubit_id}_readout")
        # data = instrument.sweep(frequencies=freqs, power=drive_power)

        # 模拟数据（实际使用时替换为真实测量）
        f01_true = freq_center + np.random.uniform(-50e6, 50e6)
        gamma = 2e6
        A = 0.1
        offset = 0.5
        noise = 0.01

        data = lorentzian(freqs, f01_true, A, gamma, offset)
        data += np.random.randn(num_points) * noise

        # 峰值检测
        peaks, properties = find_peaks(np.abs(data - offset), prominence=0.01)

        if len(peaks) > 0:
            main_peak_idx = peaks[np.argmax(properties['prominences'])]
            f01 = freqs[main_peak_idx]
            peak_height = data[main_peak_idx] - offset
            half_max = offset + peak_height / 2
            above_half = data > half_max
            indices = np.where(above_half)[0]
            fwhm = freqs[indices[-1]] - freqs[indices[0]] if len(indices) > 0 else gamma * 2
            signal = np.max(np.abs(data - offset))
            noise_std = np.std(data[:50])
            snr = 20 * np.log10(signal / noise_std) if noise_std > 0 else 0
        else:
            f01 = freq_center
            fwhm = freq_span
            snr = 0

        # 为每个qubit创建一个dataset
        datasets.append({
            'frequencies': freqs,
            'amplitudes': data,
            'qubit_id': qubit_id,
            'drive_power': drive_power,
        })

        # 汇总结果
        summary[qubit_id] = {
            'f01': float(f01),
            'fwhm': float(fwhm),
            'snr': float(snr),
            'peak_detected': len(peaks) > 0,
        }

    # 使用 datasets（复数）格式返回
    return {
        'datasets': datasets,  # 多个dataset的列表
        'summary': summary,
        'measured_qubits': qubit_ids,
    }
```
