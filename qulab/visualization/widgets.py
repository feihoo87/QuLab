"""可视化交互组件模块，提供 Matplotlib 图表的交互式工具。"""

import threading

import matplotlib.pyplot as plt
import numpy as np


class DataPicker:  # pylint: disable=too-many-instance-attributes
    """交互式数据点选取工具，支持鼠标和触摸板操作。

    多子图支持：
    当存在多个 DataPicker 实例时，只有最近进行添加/删除操作的 picker
    会响应 'z'（撤销）和 'r'（重做）快捷键。其他 picker 保持其状态不变。

    DataPicker 提供了一个交互式界面，支持多种添加/删除点的方式：
    - 轻点/鼠标左键：添加数据点
    - 长按（0.5秒）/鼠标右键：删除附近的已有数据点
    - 'z' 键：撤销上一步操作
    - 'r' 键：重做上一步撤销的操作
    - 'a' 键：切换选取模式（pick 模式 vs 默认模式）

    被选中的点会按 x 坐标排序后存储，可通过 get_xy() 方法获取。

    Attributes:
        ax: Matplotlib Axes 对象，用于交互的坐标轴
        mode: 当前模式，'pick' 表示选取模式，'default' 表示默认模式
        points_and_text: 字典，存储选取的点坐标和对应的文本标签
        points: Matplotlib Line2D 对象，显示所有选取的点
        undo_stack: 列表，存储操作历史用于撤销
        redo_stack: 列表，存储撤销的操作用于重做
        long_press_threshold: 长按检测阈值（秒），默认 0.5 秒

    Examples:
        >>> import matplotlib.pyplot as plt
        >>> import numpy as np
        >>> from qulab.visualization.widgets import DataPicker
        >>>
        >>> fig, ax = plt.subplots()
        >>> x = np.linspace(0, 10, 100)
        >>> ax.plot(x, np.sin(x))
        >>>
        >>> picker = DataPicker(ax)  # 创建选取器
        >>> plt.show()  # 显示图表，开始交互选取
        >>>
        >>> # 轻点/左键添加点，长按/右键删除点
        >>> # 'z' 撤销，'r' 重做
        >>>
        >>> x_selected, y_selected = picker.get_xy()
        >>> print(f"选取了 {len(x_selected)} 个点")

    Note:
        - 在 'pick' 模式下，支持轻点/左键添加点，长按/右键删除点
        - 按 'a' 键可在 'pick' 模式和 'default' 模式之间切换
        - 在 'default' 模式下，鼠标交互恢复正常，不会添加或删除点
        - 撤销/重做仅支持添加和删除操作，不支持模式切换
    """

    # 类变量：跟踪最近操作的 DataPicker 实例
    _active_picker = None

    def __init__(self, ax=None, long_press_threshold=0.5, on_changed=None):
        """初始化 DataPicker。

        Args:
            ax: Matplotlib Axes 对象，如果为 None 则使用当前坐标轴 plt.gca()
            long_press_threshold: 长按检测阈值（秒），默认 0.5 秒
            on_changed: 数据变化时的回调函数，会在添加点、删除点、撤销、
                重做操作后被调用。函数签名为 `on_changed(picker)`，其中
                picker 是当前 DataPicker 实例。

        Examples:
            >>> import matplotlib.pyplot as plt
            >>> import numpy as np
            >>> from qulab.visualization.widgets import DataPicker
            >>>
            >>> fig, ax = plt.subplots()
            >>> x = np.linspace(0, 10, 100)
            >>> ax.plot(x, np.sin(x))
            >>>
            >>> # 示例：自动拟合二次函数并绘制拟合曲线
            >>>
            >>> def on_changed(picker):
            ...     x_data, y_data = picker.get_xy()
            ...
            ...     # 如果点数大于等于4，进行二次函数拟合
            ...     if len(x_data) >= 4:
            ...         # 二次函数拟合: y = ax^2 + bx + c
            ...         coeffs = np.polyfit(x_data, y_data, 2)
            ...         p = np.poly1d(coeffs)
            ...
            ...         # 生成拟合曲线的 x 值
            ...         x_fit = np.linspace(x_data.min(), x_data.max(), 100)
            ...         y_fit = p(x_fit)
            ...
            ...         # 更新或创建拟合曲线
            ...         if picker.namespace.get('fit_line', None) is None:
            ...             fit_line, = ax.plot(x_fit, y_fit, 'g--',
            ...                                 label='Quadratic fit')
            ...             picker.namespace['fit_line'] = fit_line
            ...         else:
            ...             picker.namespace['fit_line'].set_data(x_fit, y_fit)
            ...     else:
            ...         # 点数不足时删除拟合曲线
            ...         if picker.namespace.get('fit_line', None) is not None:
            ...             picker.namespace['fit_line'].remove()
            ...             picker.namespace['fit_line'] = None
            ...
            >>> picker = DataPicker(ax, on_changed=on_changed)
            >>> plt.show()
        """
        self.points_and_text = {}
        self.points = None
        self.hline = None
        self.vline = None
        self.text = None
        if ax is None:
            ax = plt.gca()
        self.ax = ax
        self.mode = 'pick'

        # 长按检测相关属性
        self.long_press_threshold = long_press_threshold
        self.long_press_timer = None
        self.pending_point = None
        self.is_long_press = False
        self._press_start_time = None

        # 撤销/重做栈
        self.undo_stack = []
        self.redo_stack = []

        # 数据变化回调函数
        self.on_changed = on_changed

        # 绑定事件
        self.ax.figure.canvas.mpl_connect('button_press_event', self.on_click)
        self.ax.figure.canvas.mpl_connect('button_release_event',
                                          self.on_release)
        self.ax.figure.canvas.mpl_connect('key_press_event', self.on_key_press)
        self.namespace = {}  # 用于存储用户自定义的变量供 on_changed 回调函数使用

    def _set_active(self):
        """将当前 picker 设为激活状态（最近操作）。"""
        DataPicker._active_picker = self

    def _trigger_changed(self):
        """触发数据变化回调函数。"""
        if self.on_changed is not None:
            self.on_changed(self)

    def on_key_press(self, event):
        """处理键盘按键事件。

        支持的快捷键：
        - 'z': 撤销上一步操作（仅当本 picker 是最近操作的 picker 时生效）
        - 'r': 重做上一步撤销的操作（仅当本 picker 是最近操作的 picker 时生效）
        - 'a': 切换选取模式（全局生效）

        Args:
            event: Matplotlib KeyEvent 对象，包含按键信息
        """
        if event.key == 'z':
            # 只有最近操作的 picker 响应撤销
            if DataPicker._active_picker is self:
                self.undo()
        elif event.key == 'r':
            # 只有最近操作的 picker 响应重做
            if DataPicker._active_picker is self:
                self.redo()
        elif event.key == 'a':
            # 切换模式（全局生效）
            if self.mode != 'pick':
                self.mode = 'pick'
            else:
                self.mode = 'default'

    def on_click(self, event):
        """处理鼠标点击/触摸板按下事件。

        在 'pick' 模式下：
        - 鼠标左键（button=1）/轻点：添加数据点
        - 点击已存在的点：启动长按检测定时器
        - 鼠标右键（button=3）：删除距离点击位置 10 像素内的数据点

        Args:
            event: Matplotlib MouseEvent 对象，包含点击位置和按钮信息
        """
        if self.mode != 'pick' or event.inaxes is not self.ax:
            return

        # 鼠标右键直接删除点
        if event.button == 3:
            self._try_remove_at(event.xdata, event.ydata, event.x, event.y)
            return

        # 只处理左键
        if event.button != 1:
            return

        # 检查是否点击了已存在的点
        existing_point = self._find_nearby_point(event.xdata, event.ydata)

        if existing_point:
            # 点击了已存在的点，启动长按检测
            self.is_long_press = False
            self._start_long_press_timer(existing_point)
        else:
            # 点击空白处，记录位置用于检测是否是轻点
            self.pending_point = (event.xdata, event.ydata)

    def on_release(self, event):
        """处理鼠标释放/触摸板抬起事件。

        如果是长按则忽略（长按已在定时器中处理删除），
        否则根据位置添加新点。

        Args:
            event: Matplotlib MouseEvent 对象
        """
        if self.mode != 'pick' or event.inaxes is not self.ax:
            self._cancel_long_press_timer()
            return

        if event.button not in (1, 3):
            self._cancel_long_press_timer()
            return

        # 取消长按定时器
        self._cancel_long_press_timer()

        if self.is_long_press:
            # 长按已触发删除，重置状态
            self.is_long_press = False
            self.pending_point = None
            return

        # 检查是否是点击空白处添加新点（左键轻点）
        if event.button == 1 and self.pending_point:
            xdata, ydata = self.pending_point
            existing = self._find_nearby_point(xdata, ydata)
            if not existing:
                self._add_point(xdata, ydata)

        self.pending_point = None

    def _find_nearby_point(self, xdata, ydata, pixel_threshold=20):
        """查找距离给定坐标最近的点。

        Args:
            xdata: 数据坐标 x
            ydata: 数据坐标 y
            pixel_threshold: 像素距离阈值，默认 20 像素

        Returns:
            tuple or None: 找到的点坐标 (x, y) 或 None
        """
        if not self.points_and_text:
            return None

        for point in self.points_and_text:
            px_display, py_display = self.ax.transData.transform(point)
            x_display, y_display = self.ax.transData.transform((xdata, ydata))

            distance = np.sqrt((px_display - x_display)**2 +
                               (py_display - y_display)**2)
            if distance < pixel_threshold:
                return point
        return None

    def _start_long_press_timer(self, point):
        """启动长按检测定时器。

        Args:
            point: 待检测的点坐标
        """
        self.pending_point = point
        self.long_press_timer = threading.Timer(self.long_press_threshold,
                                                self._on_long_press)
        self.long_press_timer.start()

    def _cancel_long_press_timer(self):
        """取消长按检测定时器。"""
        if self.long_press_timer:
            self.long_press_timer.cancel()
            self.long_press_timer = None

    def _on_long_press(self):
        """长按事件处理函数。"""
        self.is_long_press = True
        if self.pending_point and self.pending_point in self.points_and_text:
            self._remove_point(self.pending_point)

    def _try_remove_at(self, _xdata, _ydata, xdisplay, ydisplay):
        """尝试删除指定位置的点（用于右键点击）。

        Args:
            _xdata: 数据坐标 x（未使用）
            _ydata: 数据坐标 y（未使用）
            xdisplay: 屏幕坐标 x（像素）
            ydisplay: 屏幕坐标 y（像素）
        """
        for point, _ in list(self.points_and_text.items()):
            point_xdisplay, point_ydisplay = self.ax.transData.transform_point(
                point)

            distance = np.sqrt((point_xdisplay - xdisplay)**2 +
                               (point_ydisplay - ydisplay)**2)
            if distance < 10:
                self._remove_point(point)
                break

    def _add_point(self, xdata, ydata):
        """添加新点并记录到撤销栈。

        同时将当前 picker 设为激活状态。

        Args:
            xdata: 点的 x 坐标
            ydata: 点的 y 坐标
        """
        point = (xdata, ydata)

        # 检查点是否已存在
        if point in self.points_and_text:
            return

        # 设为激活 picker
        self._set_active()

        # 创建文本标签
        text = self.ax.text(point[0],
                            point[1],
                            f'({point[0]:.2f}, {point[1]:.2f})',
                            verticalalignment='center')

        self.points_and_text[point] = text

        # 记录操作到撤销栈
        self.undo_stack.append(('add', point))
        self.redo_stack.clear()

        # 更新显示
        x, y = self.get_xy()
        if self.points is None:
            self.points, = self.ax.plot(x, y, 'ro')
        else:
            self.points.set_data(x, y)

        self._trigger_changed()
        self.ax.figure.canvas.draw()

    def _remove_point(self, point):
        """删除指定点并记录到撤销栈。

        同时将当前 picker 设为激活状态。

        Args:
            point: 要删除的点坐标 (x, y)
        """
        if point not in self.points_and_text:
            return

        # 设为激活 picker
        self._set_active()

        # 记录操作到撤销栈
        self.undo_stack.append(('remove', point, self.points_and_text[point]))
        self.redo_stack.clear()

        # 删除点
        text = self.points_and_text.pop(point)
        text.remove()

        # 更新显示
        if self.points_and_text:
            x, y = self.get_xy()
            self.points.set_data(x, y)
        else:
            self.points.remove()
            self.points = None

        self._trigger_changed()
        self.ax.figure.canvas.draw()

    def undo(self):
        """撤销上一步操作。

        只有当前 picker 是最近操作的 picker 时才会执行撤销。
        按 'z' 键触发。
        """
        if DataPicker._active_picker is not self:
            return
        if not self.undo_stack:
            return

        action = self.undo_stack.pop()

        if action[0] == 'add':
            # 撤销添加操作：删除该点
            point = action[1]
            if point in self.points_and_text:
                text = self.points_and_text.pop(point)
                text.remove()
                self.redo_stack.append(('add', point))
        elif action[0] == 'remove':
            # 撤销删除操作：恢复该点
            point, text = action[1], action[2]
            self.points_and_text[point] = text
            self.ax.add_artist(text)
            self.redo_stack.append(('remove', point, text))

        # 更新显示
        if self.points_and_text:
            x, y = self.get_xy()
            if self.points is None:
                self.points, = self.ax.plot(x, y, 'ro')
            else:
                self.points.set_data(x, y)
        else:
            if self.points:
                self.points.remove()
                self.points = None

        self._trigger_changed()
        self.ax.figure.canvas.draw()

    def redo(self):
        """重做上一步撤销的操作。

        只有当前 picker 是最近操作的 picker 时才会执行重做。
        按 'r' 键触发。
        """
        if DataPicker._active_picker is not self:
            return
        if not self.redo_stack:
            return

        action = self.redo_stack.pop()

        if action[0] == 'add':
            # 重做添加操作
            point = action[1]
            if point not in self.points_and_text:
                text = self.ax.text(point[0],
                                    point[1],
                                    f'({point[0]:.2f}, {point[1]:.2f})',
                                    verticalalignment='center')
                self.points_and_text[point] = text
                self.undo_stack.append(('add', point))
        elif action[0] == 'remove':
            # 重做删除操作
            point, text = action[1], action[2]
            if point in self.points_and_text:
                self.points_and_text.pop(point)
                text.remove()
                self.undo_stack.append(('remove', point, text))

        # 更新显示
        if self.points_and_text:
            x, y = self.get_xy()
            if self.points is None:
                self.points, = self.ax.plot(x, y, 'ro')
            else:
                self.points.set_data(x, y)
        else:
            if self.points:
                self.points.remove()
                self.points = None

        self._trigger_changed()
        self.ax.figure.canvas.draw()

    def get_xy(self):
        """获取已选取的所有数据点坐标。

        Returns:
            tuple: (x, y) 两个 numpy 数组，按 x 坐标升序排列。
                   如果没有选取任何点，返回两个空数组。

        Examples:
            >>> picker = DataPicker(ax)
            >>> # ... 在图表上选取一些点 ...
            >>> x, y = picker.get_xy()
            >>> print(f"选取了 {len(x)} 个点")
            >>> # x 和 y 已按 x 坐标排序
        """
        if self.points_and_text:
            data = np.asarray(list(self.points_and_text.keys()))
            x, y = data[:, 0], data[:, 1]

            index = np.argsort(x)
            x = np.asarray(x)[index]
            y = np.asarray(y)[index]
            return x, y
        return np.array([]), np.array([])
