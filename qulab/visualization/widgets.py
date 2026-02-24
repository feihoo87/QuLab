"""可视化交互组件模块，提供 Matplotlib 图表的交互式工具。"""

import threading
from typing import Callable, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np


def _guess_initial_params(
    fit_func: Callable,
    x_data: np.ndarray,
    y_data: np.ndarray,
    n_attempts: int = 10
) -> Tuple[Optional[np.ndarray], float]:
    """通过随机尝试猜测最优初始参数。

    Args:
        fit_func: 拟合函数，签名为 fit_func(x, *params) -> y
        x_data: x 坐标数据
        y_data: y 坐标数据
        n_attempts: 随机尝试次数

    Returns:
        tuple: (最优初始参数, 该初始参数对应的残差平方和)
               如果所有尝试都失败，返回 (None, inf)
    """
    # 根据数据范围估计参数的数量级
    y_range = np.ptp(y_data) if len(y_data) > 0 else 1.0
    x_range = np.ptp(x_data) if len(x_data) > 0 else 1.0

    # 尝试确定函数需要的参数个数
    # 通过传入不同数量的参数来测试
    n_params = None
    for n in range(1, 10):
        try:
            test_params = np.zeros(n)
            fit_func(x_data[:1] if len(x_data) > 0 else np.array([0]), *test_params)
            n_params = n
            break
        except TypeError:
            continue

    if n_params is None:
        # 无法确定参数个数，返回 None
        return None, float('inf')

    best_params = None
    best_residual = float('inf')

    for _ in range(n_attempts):
        # 生成随机初始参数，范围基于数据
        # 使用对数尺度覆盖不同数量级
        random_params = np.random.randn(n_params)

        # 根据参数位置调整尺度（第一个参数通常是幅度，后面的可能是频率、相位等）
        scales = []
        for i in range(n_params):
            if i == 0:
                scales.append(y_range * (0.5 + np.abs(random_params[i])))
            elif i == 1 and x_range > 0:
                scales.append(2 * np.pi / x_range * (0.5 + np.abs(random_params[i])))
            else:
                scales.append(1.0 + np.abs(random_params[i]))
        scales = np.array(scales)

        # 随机符号
        signs = np.random.choice([-1, 1], n_params)
        initial_guess = signs * scales

        try:
            y_pred = fit_func(x_data, *initial_guess)
            residual = np.sum((y_data - y_pred) ** 2)

            if residual < best_residual:
                best_residual = residual
                best_params = initial_guess.copy()
        except (ValueError, RuntimeError, OverflowError):
            continue

    return best_params, best_residual


class DataPicker:  # pylint: disable=too-many-instance-attributes
    """交互式数据点选取工具，支持鼠标和触摸板操作。

    多子图支持：
    当存在多个 DataPicker 实例时，只有最近进行添加/删除操作的 picker
    会响应 'z'（撤销）和 'r'（重做）快捷键。其他 picker 保持其状态不变。

    DataPicker 提供了一个交互式界面，支持多种添加/删除点的方式：
    - 轻点/鼠标左键：添加数据点
    - 长按（0.5秒）/鼠标右键：删除附近的已有数据点
    - 'z' 键：撤销上一步操作（仅激活的 picker 响应）
    - 'r' 键：重做上一步撤销的操作（仅激活的 picker 响应）
    - 'a' 键：切换选取模式（全局生效）
    - 'c' 键：切换坐标标签显示（黑色 -> 隐藏 -> 白色，仅激活的 picker 响应）
    - 'f' 键：强制重新拟合（仅当设置了拟合函数时生效，仅激活的 picker 响应）

    拟合功能：
    通过 set_fitter() 方法配置拟合函数后，当选中的数据点达到最小数量时，
    会自动进行曲线拟合并在图表上显示拟合曲线。拟合结果存储在 namespace 中，
    可通过 namespace['fit_result'] 访问。

    被选中的点会按 x 坐标排序后存储，可通过 get_xy() 方法获取。

    Attributes:
        ax: Matplotlib Axes 对象，用于交互的坐标轴
        mode: 当前模式，'pick' 表示选取模式，'default' 表示默认模式
        coord_display: 坐标标签显示模式，'white'、'black' 或 'hidden'
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
        >>> # 'z' 撤销，'r' 重做，'c' 切换坐标显示
        >>>
        >>> x_selected, y_selected = picker.get_xy()
        >>> print(f"选取了 {len(x_selected)} 个点")

    Note:
        - 在 'pick' 模式下，支持轻点/左键添加点，长按/右键删除点
        - 按 'a' 键可在 'pick' 模式和 'default' 模式之间切换
        - 按 'c' 键可在坐标标签的黑色、隐藏、白色三种状态间循环切换（仅激活的 picker 响应）
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
        self.coord_display = 'black'  # 坐标显示模式: 'white', 'black', 'hidden'

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

        # 拟合相关属性（由 set_fitter 方法配置）
        self._fit_func = None
        self._fit_min_points = 3
        self._fit_initial_params = None
        self._fit_n_guesses = 10
        self._fit_refit_noise = 0.1
        self._fit_line_style = 'g--'
        self._fit_line_label = None
        self._fit_last_params = None

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
        - 'c': 切换坐标标签显示模式（白色 -> 黑色 -> 隐藏）
        - 'f': 强制重新拟合（仅当本 picker 设置了拟合函数时生效）

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
        elif event.key == 'c':
            # 切换坐标显示模式（仅激活的 picker 响应）
            if DataPicker._active_picker is self:
                self.cycle_coord_display()
        elif event.key == 'f':
            # 强制重新拟合（仅激活的 picker 响应）
            if DataPicker._active_picker is self and hasattr(self, '_fit_func'):
                self.refit()

    def cycle_coord_display(self):
        """循环切换坐标标签显示模式。

        模式循环顺序：黑色 -> 隐藏 -> 白色 -> 黑色
        更新所有现有坐标标签的显示状态。
        """
        # 切换到下一个模式
        if self.coord_display == 'black':
            self.coord_display = 'hidden'
        elif self.coord_display == 'hidden':
            self.coord_display = 'white'
        else:  # white
            self.coord_display = 'black'

        # 更新所有坐标标签的显示
        self._update_coord_display()

    def _update_coord_display(self):
        """更新所有坐标标签的显示状态。

        根据当前的 coord_display 模式更新所有文本标签：
        - 'white': 白色文字
        - 'black': 黑色文字
        - 'hidden': 隐藏标签
        """
        for _point, text in self.points_and_text.items():
            if self.coord_display == 'white':
                text.set_visible(True)
                text.set_color('white')
            elif self.coord_display == 'black':
                text.set_visible(True)
                text.set_color('black')
            else:  # hidden
                text.set_visible(False)

        self.ax.figure.canvas.draw()

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

        # 创建文本标签，根据当前显示模式设置颜色和可见性
        text = self._create_coord_text(point)
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

    def _create_coord_text(self, point):
        """根据当前显示模式创建坐标文本标签。

        Args:
            point: 点坐标 (x, y)

        Returns:
            Matplotlib Text 对象
        """
        x, y = point
        label = f'({x:.2f}, {y:.2f})'
        if self.coord_display == 'white':
            return self.ax.text(x, y, label, verticalalignment='center', color='white')
        if self.coord_display == 'black':
            return self.ax.text(x, y, label, verticalalignment='center', color='black')
        # hidden
        return self.ax.text(x, y, label, verticalalignment='center', visible=False)

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
                text = self._create_coord_text(point)
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

    def set_fitter(
        self,
        fit_func: Callable,
        min_points: int = 3,
        initial_params: Optional[np.ndarray] = None,
        n_initial_guesses: int = 10,
        refit_noise_scale: float = 0.1,
        fit_line_style: str = 'g--',
        fit_line_label: Optional[str] = None,
    ):
        """配置实时拟合功能。

        当选中的数据点数量达到 min_points 时，会自动使用 fit_func 进行拟合，
        并在图表上显示拟合曲线。拟合结果存储在 picker.namespace 中。

        快捷键：
        - 'f': 强制重新拟合（即使数据点没有变化）

        Args:
            fit_func: 拟合函数，签名为 fit_func(x, *params) -> y
            min_points: 触发拟合的最小数据点数，默认 3
            initial_params: 初始拟合参数，如果为 None 则自动猜测
            n_initial_guesses: 自动猜测初始参数时的随机尝试次数，默认 10
            refit_noise_scale: 重新拟合时在现有参数周围添加的噪声尺度，默认 0.1
            fit_line_style: 拟合曲线的线型，默认 'g--'（绿色虚线）
            fit_line_label: 拟合曲线的图例标签，默认为 None

        Examples:
            >>> import matplotlib.pyplot as plt
            >>> import numpy as np
            >>> from qulab.visualization.widgets import DataPicker
            >>>
            >>> fig, ax = plt.subplots()
            >>> x = np.linspace(0, 10, 100)
            >>> ax.plot(x, np.sin(x) + 0.1 * np.random.randn(100))
            >>>
            >>> # 定义拟合函数（正弦函数）
            >>> def sin_fit(x, amplitude, frequency, phase, offset):
            ...     return amplitude * np.sin(2 * np.pi * frequency * x + phase) + offset
            >>>
            >>> picker = DataPicker(ax)
            >>> picker.set_fitter(
            ...     sin_fit,
            ...     min_points=4,
            ...     fit_line_label='Sine fit'
            ... )
            >>> plt.show()
            >>>
            >>> # 选取4个或更多点后，会自动显示拟合曲线
            >>> # 按 'f' 键可强制重新拟合
            >>>
            >>> # 获取拟合结果
            >>> fit_result = picker.namespace.get('fit_result')
            >>> if fit_result:
            ...     print(f"拟合参数: {fit_result['params']}")
            ...     print(f"拟合优度 (R²): {fit_result['r_squared']:.4f}")
        """
        self._fit_func = fit_func
        self._fit_min_points = min_points
        self._fit_initial_params = initial_params
        self._fit_n_guesses = n_initial_guesses
        self._fit_refit_noise = refit_noise_scale
        self._fit_line_style = fit_line_style
        self._fit_line_label = fit_line_label
        self._fit_last_params = None  # 存储上次成功的拟合参数

        # 设置 on_changed 回调
        self.on_changed = self._on_changed_with_fit

    def _do_fit(self, force: bool = False) -> bool:
        """执行拟合并更新图表。

        Args:
            force: 是否强制重新拟合，即使数据点没有变化

        Returns:
            bool: 拟合是否成功
        """
        if not hasattr(self, '_fit_func'):
            return False

        x_data, y_data = self.get_xy()

        if len(x_data) < self._fit_min_points:
            # 点数不足，移除拟合曲线
            fit_line = self.namespace.get('fit_line')
            if fit_line is not None:
                fit_line.remove()
                self.namespace['fit_line'] = None
                self.namespace['fit_result'] = None
                self.ax.figure.canvas.draw()
            return False

        # 尝试使用 scipy 进行拟合
        try:
            from scipy.optimize import curve_fit

            # 确定初始参数
            if self._fit_initial_params is not None and not force:
                # 用户提供了初始参数且不是强制重新拟合
                initial_guess = self._fit_initial_params
            elif self._fit_last_params is not None and not force:
                # 使用上次成功的参数，添加小量噪声以寻找更好的解
                noise = np.random.randn(len(self._fit_last_params)) * self._fit_refit_noise
                initial_guess = self._fit_last_params * (1 + noise)
            else:
                # 自动猜测初始参数
                initial_guess, _ = _guess_initial_params(
                    self._fit_func, x_data, y_data, self._fit_n_guesses
                )
                if initial_guess is None:
                    return False

            # 执行拟合
            params, pcov = curve_fit(self._fit_func, x_data, y_data, p0=initial_guess)

            # 计算拟合优度 R²
            y_pred = self._fit_func(x_data, *params)
            ss_res = np.sum((y_data - y_pred) ** 2)
            ss_tot = np.sum((y_data - np.mean(y_data)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 1.0

            # 存储拟合结果
            self._fit_last_params = params.copy()
            fit_result = {
                'params': params,
                'covariance': pcov,
                'r_squared': r_squared,
                'std_errors': np.sqrt(np.diag(pcov)) if pcov is not None else None,
            }
            self.namespace['fit_result'] = fit_result

            # 生成拟合曲线的数据点
            x_fit = np.linspace(x_data.min(), x_data.max(), 200)
            y_fit = self._fit_func(x_fit, *params)

            # 更新或创建拟合曲线
            fit_line = self.namespace.get('fit_line')
            if fit_line is None:
                fit_line, = self.ax.plot(
                    x_fit, y_fit, self._fit_line_style,
                    label=self._fit_line_label
                )
                self.namespace['fit_line'] = fit_line
            else:
                fit_line.set_data(x_fit, y_fit)

            self.ax.figure.canvas.draw()
            return True

        except ImportError:
            # scipy 未安装
            print("Warning: scipy is required for fitting. Install with: pip install scipy")
            return False
        except (RuntimeError, ValueError, OverflowError):
            # 拟合失败
            return False

    def _on_changed_with_fit(self, picker):
        """on_changed 回调函数，包含拟合逻辑。"""
        self._do_fit(force=False)

    def refit(self):
        """强制重新拟合当前数据。

        会清除上次的拟合参数记忆，重新进行初始参数猜测和拟合。
        按 'f' 键触发。
        """
        if hasattr(self, '_fit_func'):
            self._fit_last_params = None
            self._do_fit(force=True)
