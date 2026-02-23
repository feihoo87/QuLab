#!/usr/bin/env python3
"""
demo_local.py - 本地调用 qulab.storage 使用示例

此示例展示如何在本地直接使用 LocalStorage 进行数据存储和管理。
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from qulab.storage import LocalStorage


def demo_basic_document():
    """演示文档的基本操作"""
    print("=" * 60)
    print("演示 1: 文档基本操作")
    print("=" * 60)

    # 创建临时存储目录
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(tmpdir)

        # 创建文档
        doc_ref = storage.create_document(
            name="qubit_calibration",
            data={"f01": 5.2e9, "t1": 100e-6, "t2": 50e-6},
            state="ok",
            tags=["calibration", "qubit", "Q1"]
        )
        print(f"创建文档: ID={doc_ref.id}, Name={doc_ref.name}")

        # 获取文档
        doc = doc_ref.get()
        print(f"文档数据: {doc.data}")
        print(f"文档标签: {doc.tags}")
        print(f"文档状态: {doc.state}")
        print(f"创建时间: {doc.ctime}")

        # 创建带分析代码的文档
        doc_ref2 = storage.create_document(
            name="resonator_analysis",
            data={"fit_result": {"f0": 5.001e9, "Q": 10000}},
            state="ok",
            tags=["analysis", "resonator"],
            script='''
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

def lorentzian(f, f0, Q, A, offset):
    return A / (1 + 4*Q**2*((f-f0)/f0)**2) + offset

# 拟合数据
popt, _ = curve_fit(lorentzian, freq, amplitude, p0=[5e9, 10000, 1, 0])
print(f"Resonator frequency: {popt[0]/1e9:.3f} GHz")
print(f"Quality factor: {popt[1]:.0f}")
'''
        )
        doc2 = doc_ref2.get()
        print(f"\n带代码的文档:")
        print(f"  Script Hash: {doc2.script_hash}")
        print(f"  Script 前100字符: {doc2.script[:100]}...")


def demo_query_documents():
    """演示文档查询操作"""
    print("\n" + "=" * 60)
    print("演示 2: 文档查询操作")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(tmpdir)

        # 批量创建文档
        for i in range(5):
            storage.create_document(
                name=f"experiment_{i:03d}",
                data={"index": i, "value": np.random.rand()},
                state="ok" if i % 2 == 0 else "error",
                tags=["batch", "experiment"]
            )

        # 创建一些带特定标签的文档
        storage.create_document(
            name="calibration_001",
            data={"f01": 5.2e9},
            state="ok",
            tags=["calibration"]
        )

        # 查询所有文档
        print("\n所有文档:")
        for doc_ref in storage.query_documents(limit=100):
            doc = doc_ref.get()
            print(f"  {doc.id}: {doc.name} [{doc.state}]")

        # 按名称模式查询
        print("\n名称匹配 'exp*' 的文档:")
        for doc_ref in storage.query_documents(name="exp*"):
            doc = doc_ref.get()
            print(f"  {doc.id}: {doc.name}")

        # 按标签查询
        print("\n标签包含 'calibration' 的文档:")
        for doc_ref in storage.query_documents(tags=["calibration"]):
            doc = doc_ref.get()
            print(f"  {doc.id}: {doc.name}")

        # 按状态查询
        print("\n状态为 'ok' 的文档:")
        for doc_ref in storage.query_documents(state="ok"):
            doc = doc_ref.get()
            print(f"  {doc.id}: {doc.name}")

        # 计数
        count = storage.count_documents()
        print(f"\n总文档数: {count}")


def demo_dataset():
    """演示数据集操作"""
    print("\n" + "=" * 60)
    print("演示 3: 数据集操作")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(tmpdir)

        # 创建带配置和代码的数据集
        config = {
            "qubit": "Q1",
            "frequency": {"start": 5.0e9, "stop": 5.1e9, "points": 101},
            "power": {"drive": -20, "readout": -30},
            "averages": 1000
        }

        measurement_script = '''
import numpy as np
from qulab import mw_source, digitizer

def measure(freq, power_drive, power_readout, averages):
    mw_source.set_frequency(freq)
    mw_source.set_power(power_drive)
    data = digitizer.acquire(averages)
    return np.mean(data), np.std(data)
'''

        ds_ref = storage.create_dataset(
            name="qubit_resonator_scan",
            description={"type": "resonator_scan", "qubit": "Q1"},
            config=config,
            script=measurement_script
        )
        print(f"创建数据集: ID={ds_ref.id}, Name={ds_ref.name}")

        # 获取数据集
        ds = ds_ref.get()
        print(f"数据集描述: {ds.description}")
        print(f"Config Hash: {ds.config_hash}")
        print(f"配置内容: {ds.config}")

        # 追加数据
        print("\n追加数据点...")
        for i in range(10):
            ds.append(
                position=(0, i),
                data={"frequency": 5.0e9 + i * 10e6, "amplitude": np.random.rand(), "phase": np.random.rand()}
            )
        ds.flush()

        # 查看数组
        print(f"\n数据集中的数组: {ds.keys()}")

        # 读取数组
        freq_array = ds.get_array("frequency")
        print(f"频率数组值: {freq_array.value()}")

        # 转换为 numpy 数组
        amp_array = ds.get_array("amplitude")
        amp_data = amp_array.toarray()
        print(f"幅度数组形状: {amp_data.shape}")
        print(f"幅度数据: {amp_data}")


def demo_dataset_batch():
    """演示数据集批量操作"""
    print("\n" + "=" * 60)
    print("演示 4: 数据集批量操作")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(tmpdir)

        # 创建数据集
        ds_ref = storage.create_dataset(
            name="2d_sweep",
            description={"dimensions": [10, 10]}
        )
        ds = ds_ref.get()

        # 批量追加数据
        print("批量追加 100 个数据点...")
        for i in range(10):
            for j in range(10):
                ds.append(
                    position=(i, j),
                    data={
                        "x": i * 0.1,
                        "y": j * 0.1,
                        "z": np.sin(i * 0.1) * np.cos(j * 0.1)
                    }
                )
                # 定期刷新
                if (i * 10 + j) % 20 == 0:
                    ds.flush()

        ds.flush()
        print("数据追加完成")

        # 读取数据
        z_array = ds.get_array("z")
        z_data = z_array.toarray()
        print(f"Z 数组形状: {z_data.shape}")
        print(f"Z 数据前5个: {z_data[:5]}")


def demo_document_dataset_relation():
    """演示文档与数据集的关联"""
    print("\n" + "=" * 60)
    print("演示 5: 文档与数据集关联")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(tmpdir)

        # 创建数据集
        ds_ref1 = storage.create_dataset(name="raw_data_1", description={"type": "raw"})
        ds_ref2 = storage.create_dataset(name="raw_data_2", description={"type": "raw"})

        print(f"创建数据集 1: ID={ds_ref1.id}")
        print(f"创建数据集 2: ID={ds_ref2.id}")

        # 创建文档并关联数据集
        doc_ref = storage.create_document(
            name="analysis_result",
            data={"fit_result": {"f0": 5.001e9, "Q": 10000}},
            state="ok",
            tags=["analysis"],
            datasets=[ds_ref1.id, ds_ref2.id]  # 关联数据集
        )

        doc = doc_ref.get()
        print(f"\n文档 '{doc.name}' 关联的数据集:")
        # 注意: 需要检查文档模型是否支持 datasets 属性
        # 这取决于具体的模型实现


def demo_update_document():
    """演示文档更新"""
    print("\n" + "=" * 60)
    print("演示 6: 文档更新")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(tmpdir)

        # 创建文档
        doc_ref = storage.create_document(
            name="experiment_config",
            data={"version": 1, "param": 100},
            state="ok"
        )

        doc = doc_ref.get()
        print(f"原文档: ID={doc.id}, data={doc.data}")

        # 修改数据并保存为新版本
        doc.data["version"] = 2
        doc.data["param"] = 200
        doc.state = "updated"

        new_ref = doc.save(storage)
        print(f"新版本: ID={new_ref.id}, data={new_ref.get().data}")

        # 旧版本仍然存在
        old_doc = doc_ref.get()
        print(f"旧版本: ID={old_doc.id}, data={old_doc.data}")


def main():
    """运行所有演示"""
    print("\n")
    print("*" * 60)
    print(" qulab.storage 本地使用示例")
    print("*" * 60)

    demo_basic_document()
    demo_query_documents()
    demo_dataset()
    demo_dataset_batch()
    demo_document_dataset_relation()
    demo_update_document()

    print("\n" + "=" * 60)
    print("所有演示完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
