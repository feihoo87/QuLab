QuLab Visualization - 可视化交互组件
======================================

``qulab.visualization`` 模块提供 Matplotlib 图表的交互式工具。

.. contents:: 目录
   :local:

DataPicker - 交互式数据点选取
-----------------------------

DataPicker 提供了交互式数据点选取功能，支持通过鼠标/触摸板在 Matplotlib
图表上添加和删除数据点。

快速开始
~~~~~~~~

.. code-block:: python

   import matplotlib.pyplot as plt
   import numpy as np
   from qulab.visualization.widgets import DataPicker

   fig, ax = plt.subplots()
   x = np.linspace(0, 10, 100)
   ax.plot(x, np.sin(x))

   picker = DataPicker(ax)
   plt.show()

   x_selected, y_selected = picker.get_xy()

预填充初始点
~~~~~~~~~~~~

可以通过 ``initial_points`` 参数在创建时预填充数据点，也可以通过 ``add_points``
和 ``remove_points`` 方法编程式管理数据点。

.. code-block:: python

   # 方式1：构造时传入初始点
   picker = DataPicker(ax, initial_points=([1, 2, 3], [4, 5, 6]))

   # 方式2：(x, y) 元组格式
   picker = DataPicker(ax, initial_points=([1.0, 2.0], [0.5, 0.8]))

   # 方式3：列表格式
   picker = DataPicker(ax, initial_points=[(1.0, 0.5), (2.0, 0.8)])

添加和删除数据点
~~~~~~~~~~~~~~~~

.. code-block:: python

   picker = DataPicker(ax)

   # 批量添加（record=True 记录到撤销栈）
   picker.add_points([1, 2, 3, 4, 5], [0.5, 0.8, 0.3, -0.2, -0.6])

   # 批量添加（record=False 不记录撤销，适合初始数据填充）
   picker.add_points([6, 7], [-0.1, 0.2], record=False)

   # 批量删除
   picker.remove_points([2, 4], [0.8, -0.2])

   # 清空所有点（可撤销）
   picker.clear()

撤销与重做
~~~~~~~~~~

所有添加、删除和清空操作都会记录到撤销栈：

.. code-block:: python

   picker.add_points([1, 2, 3], [4, 5, 6])
   picker.undo()   # 撤销批量添加
   picker.redo()   # 重做批量添加

   picker.clear()
   picker.undo()   # 恢复清空前的所有点

初始点（通过 ``initial_points`` 或 ``record=False`` 添加的点）不会记录到撤销栈中。

拟合功能
~~~~~~~~

通过 ``set_fitter()`` 方法可以配置实时曲线拟合：

.. code-block:: python

   def sin_fit(x, amp, freq, phase, offset):
       return amp * np.sin(2 * np.pi * freq * x + phase) + offset

   picker = DataPicker(ax, initial_points=([0, 1, 2], [0, 0.8, 0]))
   picker.set_fitter(sin_fit, min_points=4, fit_line_label='Sine fit')

   # 添加更多点后自动触发拟合
   picker.add_points([3, 4], [-0.5, 0.3])

API 参考
~~~~~~~~

.. py:class:: DataPicker(ax=None, long_press_threshold=0.5, on_changed=None, initial_points=None)

   :param ax: Matplotlib Axes 对象
   :param long_press_threshold: 长按检测阈值（秒），默认 0.5
   :param on_changed: 数据变化回调 ``on_changed(picker)``
   :param initial_points: 初始数据点，支持 ``(x_array, y_array)`` 元组或 ``[(x1, y1), ...]`` 列表。初始点不记录到撤销栈。

   .. py:method:: add_points(x, y, record=True)
      :staticmethod:

      批量添加数据点。

      :param x: x 坐标数组
      :param y: y 坐标数组
      :param record: 是否记录到撤销栈，默认 True

   .. py:method:: remove_points(x, y)
      :staticmethod:

      批量删除指定坐标的数据点。不存在的点会被静默忽略。

      :param x: x 坐标数组
      :param y: y 坐标数组

   .. py:method:: clear()
      :staticmethod:

      清除所有数据点。操作记录到撤销栈，可通过 ``undo()`` 恢复。

   .. py:method:: get_xy()

      获取已选取的数据点，按 x 坐标升序排列。

      :returns: ``(x, y)`` numpy 数组

   .. py:method:: undo()

      撤销上一步操作。

   .. py:method:: redo()

      重做上一步撤销。

   .. py:method:: set_fitter(fit_func, min_points=3, ...)

      配置实时曲线拟合功能。选点数量达到 ``min_points`` 后自动拟合。

   .. py:method:: refit()

      强制重新拟合当前数据。
