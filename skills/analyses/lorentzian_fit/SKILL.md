---
name: lorentzian_fit
type: analysis
description: |
  对能谱数据进行洛伦兹线型拟合，提取 qubit 频率和线宽。
  适用于单峰 Lorentzian 线型的分析。

capabilities:
  排查问题:
    - 频率不确定: 通过拟合精确定位峰值
    - 线宽异常: 识别退相干问题
  提取信息:
    - qubit频率: 从谱峰位置提取
    - 退相干率: 从线宽提取 (gamma = FWHM/2)
    - 品质因数: Q = f0 / FWHM
    - 信号质量: 从拟合质量评估

inputs:
  - name: dataset_id
    type: integer
    description: 输入数据集ID（必须包含能谱数据）
    required: true
  - name: freq_key
    type: string
    description: 频率数组的键名
    default: frequencies
  - name: amp_key
    type: string
    description: 幅度数组的键名
    default: amplitudes
  - name: peak_prominence
    type: number
    description: 峰值检测阈值（相对于最大值的比值）
    default: 0.1

outputs:
  - name: f01
    type: number
    description: 拟合得到的频率 (Hz)
  - name: gamma
    type: number
    description: 半高全宽的一半 / 退相干率 (Hz)
  - name: Q
    type: number
    description: 品质因数
  - name: A
    type: number
    description: 峰值幅度
  - name: offset
    type: number
    description: 背景偏移
  - name: fit_quality
    type: string
    description: 拟合质量 (good/moderate/poor)
  - name: fit_success
    type: boolean
    description: 拟合是否成功

metadata:
  tags: [fitting, spectroscopy, analysis, lorentzian]
  estimated_time: 5
  author: auto-lab
---

```python
import numpy as np
from scipy.optimize import curve_fit
from scipy.signal import find_peaks

def lorentzian(f, f0, A, gamma, offset):
    """洛伦兹线型函数

    Args:
        f: 频率
        f0: 中心频率
        A: 峰值幅度
        gamma: 半高全宽的一半 (FWHM/2)
        offset: 背景偏移

    Returns:
        洛伦兹线型值
    """
    return offset + A * gamma**2 / ((f - f0)**2 + gamma**2)

def run(dataset_id: int, freq_key: str = 'frequencies',
        amp_key: str = 'amplitudes', peak_prominence: float = 0.1, ctx=None):
    """执行洛伦兹拟合

    Args:
        dataset_id: 数据集ID
        freq_key: 频率数组键名
        amp_key: 幅度数组键名
        peak_prominence: 峰值检测阈值
        ctx: 分析上下文

    Returns:
        包含拟合结果的字典
    """
    # 获取数据集
    ds = ctx.get_dataset(dataset_id)

    # 获取数据
    try:
        freqs = ds.get_array(freq_key).toarray()
        amps = ds.get_array(amp_key).toarray()
    except Exception as e:
        return {
            'data': {'error': f'Failed to load data: {str(e)}'},
            'state': 'error',
            'extracted_info': {'fit_success': False}
        }

    if len(freqs) == 0 or len(amps) == 0:
        return {
            'data': {'error': 'Empty data arrays'},
            'state': 'error',
            'extracted_info': {'fit_success': False}
        }

    # 峰值检测
    # 归一化幅度用于检测
    amp_normalized = np.abs(amps - np.mean(amps))
    amp_normalized = amp_normalized / np.max(amp_normalized) if np.max(amp_normalized) > 0 else amp_normalized

    peaks, properties = find_peaks(amp_normalized, prominence=peak_prominence)

    if len(peaks) == 0:
        return {
            'data': {'error': 'No peaks detected'},
            'state': 'error',
            'extracted_info': {'peak_found': False, 'fit_success': False}
        }

    # 选择最显著的峰值
    main_peak_idx = peaks[np.argmax(properties['prominences'])]
    f0_guess = freqs[main_peak_idx]
    A_guess = amps[main_peak_idx] - np.mean(amps)
    gamma_guess = (freqs[-1] - freqs[0]) / 10  # 初始猜测
    offset_guess = np.mean(amps)

    # 限制拟合范围（峰值附近的区域）
    span = (freqs[-1] - freqs[0]) / 5
    fit_mask = np.abs(freqs - f0_guess) < span

    if np.sum(fit_mask) < 10:
        fit_mask = np.ones(len(freqs), dtype=bool)  # 如果点数太少，使用全部数据

    # 执行拟合
    p0 = [f0_guess, A_guess, gamma_guess, offset_guess]
    bounds = (
        [freqs[0], -np.inf, 0, -np.inf],  # 下限
        [freqs[-1], np.inf, freqs[-1] - freqs[0], np.inf]  # 上限
    )

    try:
        popt, pcov = curve_fit(
            lorentzian,
            freqs[fit_mask],
            amps[fit_mask],
            p0=p0,
            bounds=bounds,
            maxfev=10000
        )

        f0, A, gamma, offset = popt
        fwhm = 2 * gamma

        # 计算误差
        perr = np.sqrt(np.diag(pcov))
        f0_err, A_err, gamma_err, offset_err = perr

        # 计算品质因数
        Q = f0 / fwhm if fwhm > 0 else 0

        # 计算拟合质量
        fitted_curve = lorentzian(freqs, *popt)
        residuals = amps - fitted_curve
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((amps - np.mean(amps))**2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # 评估拟合质量
        if r_squared > 0.95:
            fit_quality = 'good'
        elif r_squared > 0.85:
            fit_quality = 'moderate'
        else:
            fit_quality = 'poor'

        return {
            'data': {
                'f01': float(f0),
                'f01_error': float(f0_err),
                'gamma': float(gamma),
                'gamma_error': float(gamma_err),
                'fwhm': float(fwhm),
                'Q': float(Q),
                'A': float(A),
                'A_error': float(A_err),
                'offset': float(offset),
                'fit_quality': fit_quality,
                'r_squared': float(r_squared),
                'fit_params': {
                    'f0': float(f0),
                    'A': float(A),
                    'gamma': float(gamma),
                    'offset': float(offset)
                },
                'fit_errors': {
                    'f0': float(f0_err),
                    'A': float(A_err),
                    'gamma': float(gamma_err),
                    'offset': float(offset_err)
                }
            },
            'state': 'ok' if fit_quality in ['good', 'moderate'] else 'warning',
            'extracted_info': {
                'f01': float(f0),
                'f01_error': float(f0_err),
                'linewidth': float(fwhm),
                'gamma': float(gamma),
                'Q': float(Q),
                'fit_quality': fit_quality,
                'r_squared': float(r_squared),
                'fit_success': True
            }
        }

    except Exception as e:
        return {
            'data': {
                'error': f'Fit failed: {str(e)}',
                'peak_frequency': float(f0_guess),
            },
            'state': 'error',
            'extracted_info': {
                'fit_success': False,
                'error': str(e)
            }
        }
```
