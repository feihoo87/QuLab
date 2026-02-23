#!/usr/bin/env python3
"""
demo_client.py - 通过 Server 调用 qulab.storage 使用示例

此示例展示如何通过 RemoteStorage 连接远程服务器进行数据存储和管理。

运行前需要先启动存储服务器:
    uv run python -m qulab.storage storage server start --port 6789 --data-path /tmp/qulab_storage

或使用 Python API 启动服务器:
    from qulab.storage import LocalStorage, StorageServer
    import asyncio

    storage = LocalStorage("/tmp/qulab_storage")
    server = StorageServer(storage, host="127.0.0.1", port=6789)
    asyncio.run(server.run())
"""

import asyncio
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from qulab.storage import RemoteStorage


def demo_connect_server():
    """演示连接到服务器"""
    print("=" * 60)
    print("演示 1: 连接远程服务器")
    print("=" * 60)

    # 创建远程存储客户端
    storage = RemoteStorage("tcp://127.0.0.1:6789", timeout=30.0)

    # 检查连接
    try:
        count = storage.count_documents()
        print(f"成功连接到服务器!")
        print(f"远程存储中的文档数: {count}")
    except Exception as e:
        print(f"连接失败: {e}")
        print("\n请确保服务器已启动:")
        print("  uv run python -m qulab.storage server start --port 6789")
        return False

    return True


def demo_remote_document():
    """演示远程文档操作"""
    print("\n" + "=" * 60)
    print("演示 2: 远程文档操作")
    print("=" * 60)

    storage = RemoteStorage("tcp://127.0.0.1:6789", timeout=30.0)

    # 创建文档
    print("\n创建文档...")
    doc_ref = storage.create_document(
        name="remote_calibration",
        data={"f01": 5.2e9, "t1": 100e-6},
        state="ok",
        tags=["calibration", "remote"]
    )
    print(f"创建远程文档: ID={doc_ref.id}, Name={doc_ref.name}")

    # 获取文档数据
    print("\n获取文档数据...")
    doc_data = doc_ref.get()
    print(f"文档数据: {doc_data}")

    # 通过 ID 获取文档
    print("\n通过 ID 获取文档...")
    doc = storage.get_document(doc_ref.id)
    data = doc.get_data()
    print(f"文档数据: {data}")


def demo_remote_query():
    """演示远程查询"""
    print("\n" + "=" * 60)
    print("演示 3: 远程文档查询")
    print("=" * 60)

    storage = RemoteStorage("tcp://127.0.0.1:6789", timeout=30.0)

    # 批量创建文档
    print("\n批量创建文档...")
    for i in range(5):
        storage.create_document(
            name=f"remote_exp_{i:03d}",
            data={"index": i, "value": float(np.random.rand())},
            state="ok",
            tags=["remote", "experiment"]
        )

    # 查询所有文档
    print("\n查询所有文档 (限制10条):")
    total = 0
    for doc_ref in storage.query_documents(limit=10):
        print(f"  ID={doc_ref.id}, Name={doc_ref.name}")
        total += 1

    # 按名称查询
    print("\n名称匹配 'remote_exp_00*' 的文档:")
    for doc_ref in storage.query_documents(name="remote_exp_00*"):
        print(f"  ID={doc_ref.id}, Name={doc_ref.name}")

    # 按标签查询
    print("\n标签包含 'remote' 的文档:")
    for doc_ref in storage.query_documents(tags=["remote"], limit=100):
        print(f"  ID={doc_ref.id}, Name={doc_ref.name}")

    # 计数
    count = storage.count_documents()
    print(f"\n总文档数: {count}")

    count_with_tag = storage.count_documents(tags=["remote"])
    print(f"带 'remote' 标签的文档数: {count_with_tag}")


def demo_remote_dataset():
    """演示远程数据集操作"""
    print("\n" + "=" * 60)
    print("演示 4: 远程数据集操作")
    print("=" * 60)

    storage = RemoteStorage("tcp://127.0.0.1:6789", timeout=30.0)

    # 创建数据集
    print("\n创建远程数据集...")
    config = {
        "qubit": "Q1",
        "frequency": {
            "start": 5.0e9,
            "stop": 5.1e9,
            "points": 101
        },
    }

    ds_ref = storage.create_dataset(name="remote_resonator_scan",
                                    description={
                                        "type": "resonator_scan",
                                        "qubit": "Q1"
                                    },
                                    config=config)
    print(f"创建数据集: ID={ds_ref.id}, Name={ds_ref.name}")

    # 获取数据集信息
    print("\n获取数据集信息...")
    ds = ds_ref.get()
    info = ds.get_info()
    print(f"数据集信息: {info}")

    # 追加数据
    print("\n追加数据...")
    for j in range(5):
        for i in range(10):
            ds.append(position=(j, i),
                    data={
                        "frequency": 5.0e9 + i * 10e6,
                        "amplitude": np.random.rand(1024, 64)
                    })
    print("数据追加完成")

    # 查看数组
    print(f"\n数据集中的数组: {ds.keys()}")

    # 读取数组
    print("\n读取数组数据...")
    freq_array = ds.get_array("frequency")
    freq_data = freq_array.toarray()
    print(f"频率数组: {freq_data}")

    amp_array = ds.get_array("amplitude")
    amp_data = amp_array.toarray()
    print(f"幅度数组: {amp_data.shape}")


def demo_remote_dataset_query():
    """演示远程数据集查询"""
    print("\n" + "=" * 60)
    print("演示 5: 远程数据集查询")
    print("=" * 60)

    storage = RemoteStorage("tcp://127.0.0.1:6789", timeout=30.0)

    # 批量创建数据集
    print("\n批量创建数据集...")
    for i in range(3):
        storage.create_dataset(
            name=f"remote_scan_{i:03d}",
            description={"type": "scan", "index": i}
        )

    # 查询所有数据集
    print("\n查询所有数据集:")
    for ds_ref in storage.query_datasets(limit=100):
        print(f"  ID={ds_ref.id}, Name={ds_ref.name}")

    # 按名称查询
    print("\n名称匹配 'remote_scan*' 的数据集:")
    for ds_ref in storage.query_datasets(name="remote_scan*"):
        print(f"  ID={ds_ref.id}, Name={ds_ref.name}")

    # 计数
    count = storage.count_datasets()
    print(f"\n总数据集数: {count}")


def demo_cleanup():
    """演示清理数据"""
    print("\n" + "=" * 60)
    print("演示 6: 清理远程数据")
    print("=" * 60)

    storage = RemoteStorage("tcp://127.0.0.1:6789", timeout=30.0)

    # 删除文档
    print("\n删除带 'remote' 标签的文档...")
    deleted_docs = 0
    for doc_ref in list(storage.query_documents(tags=["remote"], limit=100)):
        if doc_ref.delete():
            print(f"  删除文档 ID={doc_ref.id}")
            deleted_docs += 1
    print(f"共删除 {deleted_docs} 个文档")

    # 删除数据集
    print("\n删除远程数据集...")
    deleted_datasets = 0
    for ds_ref in list(storage.query_datasets(name="remote_*", limit=100)):
        if ds_ref.delete():
            print(f"  删除数据集 ID={ds_ref.id}")
            deleted_datasets += 1
    print(f"共删除 {deleted_datasets} 个数据集")


def main():
    """运行所有演示"""
    print("\n")
    print("*" * 60)
    print(" qulab.storage 远程客户端使用示例")
    print("*" * 60)
    print("\n确保服务器已启动:")
    print("  uv run python -m qulab.storage server start --port 6789")
    print("\n")

    # 首先检查连接
    if not demo_connect_server():
        return

    try:
        demo_remote_document()
        demo_remote_query()
        demo_remote_dataset()
        demo_remote_dataset_query()
        demo_cleanup()

        print("\n" + "=" * 60)
        print("所有演示完成!")
        print("=" * 60)
    except Exception as e:
        print(f"\n演示过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
