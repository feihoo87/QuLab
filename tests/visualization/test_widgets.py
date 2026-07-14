"""DataPicker 组件测试。"""

import matplotlib
matplotlib.use('Agg')  # 非交互式后端，无需显示窗口

import matplotlib.pyplot as plt
import numpy as np
import pytest

from qulab.visualization.widgets import DataPicker


@pytest.fixture
def fig_ax():
    """创建测试用的 figure 和 axes。"""
    fig, ax = plt.subplots()
    ax.plot(np.linspace(0, 10, 100), np.sin(np.linspace(0, 10, 100)))
    yield fig, ax
    plt.close(fig)


class TestNormalizePoints:
    """测试 _normalize_points 静态方法。"""

    def test_tuple_format(self):
        """测试 (x_array, y_array) 格式。"""
        x, y = DataPicker._normalize_points(([1, 2, 3], [4, 5, 6]))
        np.testing.assert_array_equal(x, [1, 2, 3])
        np.testing.assert_array_equal(y, [4, 5, 6])

    def test_list_of_tuples_format(self):
        """测试 [(x1, y1), ...] 格式。"""
        x, y = DataPicker._normalize_points([(1, 4), (2, 5), (3, 6)])
        np.testing.assert_array_equal(x, [1, 2, 3])
        np.testing.assert_array_equal(y, [4, 5, 6])

    def test_2d_array_format(self):
        """测试 2D numpy 数组格式。"""
        x, y = DataPicker._normalize_points(np.array([[1, 4], [2, 5], [3, 6]]))
        np.testing.assert_array_equal(x, [1, 2, 3])
        np.testing.assert_array_equal(y, [4, 5, 6])

    def test_invalid_format(self):
        """测试无效格式抛出 ValueError。"""
        with pytest.raises(ValueError):
            DataPicker._normalize_points("invalid")
        with pytest.raises(ValueError):
            DataPicker._normalize_points(42)
        with pytest.raises(ValueError):
            DataPicker._normalize_points(np.array([1, 2, 3]))


class TestInitialPoints:
    """测试初始点功能。"""

    def test_initial_points_tuple_format(self, fig_ax):
        """测试通过 (x, y) 元组格式传入初始点。"""
        _, ax = fig_ax
        picker = DataPicker(ax, initial_points=([1, 2, 3], [4, 5, 6]))
        x, y = picker.get_xy()
        np.testing.assert_array_equal(x, [1, 2, 3])
        np.testing.assert_array_equal(y, [4, 5, 6])

    def test_initial_points_list_format(self, fig_ax):
        """测试通过列表格式传入初始点。"""
        _, ax = fig_ax
        picker = DataPicker(ax, initial_points=[(1, 4), (2, 5), (3, 6)])
        x, y = picker.get_xy()
        np.testing.assert_array_equal(x, [1, 2, 3])
        np.testing.assert_array_equal(y, [4, 5, 6])

    def test_initial_points_sorted_by_x(self, fig_ax):
        """测试初始点按 x 坐标排序返回。"""
        _, ax = fig_ax
        picker = DataPicker(ax, initial_points=([3, 1, 2], [30, 10, 20]))
        x, y = picker.get_xy()
        np.testing.assert_array_equal(x, [1, 2, 3])
        np.testing.assert_array_equal(y, [10, 20, 30])

    def test_initial_points_empty(self, fig_ax):
        """测试不传 initial_points 时为空。"""
        _, ax = fig_ax
        picker = DataPicker(ax)
        x, y = picker.get_xy()
        assert len(x) == 0
        assert len(y) == 0

    def test_initial_points_not_in_undo_stack(self, fig_ax):
        """测试初始点不记录在撤销栈中。"""
        _, ax = fig_ax
        picker = DataPicker(ax, initial_points=([1, 2], [3, 4]))
        assert len(picker.undo_stack) == 0
        # undo 应该无操作
        picker.undo()
        x, y = picker.get_xy()
        assert len(x) == 2  # 初始点不应被撤销


class TestAddPoints:
    """测试 add_points 方法。"""

    def test_add_points_basic(self, fig_ax):
        """测试基本批量添加。"""
        _, ax = fig_ax
        picker = DataPicker(ax)
        picker.add_points([1, 2, 3], [4, 5, 6])
        x, y = picker.get_xy()
        np.testing.assert_array_equal(x, [1, 2, 3])
        np.testing.assert_array_equal(y, [4, 5, 6])

    def test_add_points_no_record(self, fig_ax):
        """测试 record=False 时不记录到撤销栈。"""
        _, ax = fig_ax
        picker = DataPicker(ax)
        picker.add_points([1, 2], [3, 4], record=False)
        assert len(picker.undo_stack) == 0
        x, y = picker.get_xy()
        assert len(x) == 2

    def test_add_points_with_record(self, fig_ax):
        """测试 record=True 时记录到撤销栈。"""
        _, ax = fig_ax
        picker = DataPicker(ax)
        picker.add_points([1, 2], [3, 4], record=True)
        assert len(picker.undo_stack) == 1
        assert picker.undo_stack[0][0] == 'add_batch'

    def test_add_points_skip_duplicates(self, fig_ax):
        """测试添加重复点会被跳过。"""
        _, ax = fig_ax
        picker = DataPicker(ax)
        picker.add_points([1, 2], [3, 4])
        picker.add_points([1, 3], [3, 5])  # (1,3) 重复，(3,5) 新增
        x, y = picker.get_xy()
        assert len(x) == 3  # 2 + 1 去重后

    def test_add_points_length_mismatch(self, fig_ax):
        """测试 x/y 长度不匹配时抛出异常。"""
        _, ax = fig_ax
        picker = DataPicker(ax)
        with pytest.raises(ValueError):
            picker.add_points([1, 2], [3])

    def test_add_points_triggers_on_changed(self, fig_ax):
        """测试 add_points 触发 on_changed 回调。"""
        _, ax = fig_ax
        calls = []

        def cb(picker):
            calls.append(len(picker.get_xy()[0]))

        picker = DataPicker(ax, on_changed=cb)
        picker.add_points([1, 2], [3, 4])
        assert calls == [2]


class TestRemovePoints:
    """测试 remove_points 方法。"""

    def test_remove_points_basic(self, fig_ax):
        """测试基本批量删除。"""
        _, ax = fig_ax
        picker = DataPicker(ax, initial_points=([1, 2, 3], [4, 5, 6]))
        picker.remove_points([2], [5])
        x, y = picker.get_xy()
        np.testing.assert_array_equal(x, [1, 3])
        np.testing.assert_array_equal(y, [4, 6])

    def test_remove_points_nonexistent(self, fig_ax):
        """测试删除不存在的点被静默忽略。"""
        _, ax = fig_ax
        picker = DataPicker(ax, initial_points=([1, 2], [3, 4]))
        picker.remove_points([99], [99])
        x, y = picker.get_xy()
        assert len(x) == 2  # 不影响已有点

    def test_remove_points_length_mismatch(self, fig_ax):
        """测试 x/y 长度不匹配时抛出异常。"""
        _, ax = fig_ax
        picker = DataPicker(ax)
        with pytest.raises(ValueError):
            picker.remove_points([1, 2], [3])

    def test_remove_points_records_undo(self, fig_ax):
        """测试删除操作记录到撤销栈。"""
        _, ax = fig_ax
        picker = DataPicker(ax, initial_points=([1, 2], [3, 4]))
        picker.remove_points([1], [3])
        assert len(picker.undo_stack) == 1
        assert picker.undo_stack[0][0] == 'remove_batch'


class TestClear:
    """测试 clear 方法。"""

    def test_clear_basic(self, fig_ax):
        """测试清除所有点。"""
        _, ax = fig_ax
        picker = DataPicker(ax, initial_points=([1, 2, 3], [4, 5, 6]))
        picker.clear()
        x, y = picker.get_xy()
        assert len(x) == 0

    def test_clear_empty(self, fig_ax):
        """测试对空 picker 调用 clear 无影响。"""
        _, ax = fig_ax
        picker = DataPicker(ax)
        picker.clear()
        x, y = picker.get_xy()
        assert len(x) == 0

    def test_clear_records_undo(self, fig_ax):
        """测试 clear 记录到撤销栈且可以 undo。"""
        _, ax = fig_ax
        picker = DataPicker(ax, initial_points=([1, 2, 3], [4, 5, 6]))
        picker.clear()
        assert len(picker.undo_stack) == 1
        assert picker.undo_stack[0][0] == 'clear'
        # undo 恢复
        picker.undo()
        x, y = picker.get_xy()
        assert len(x) == 3


class TestUndoRedoBatch:
    """测试批量操作的撤销和重做。"""

    def test_undo_add_batch(self, fig_ax):
        """测试撤销批量添加。"""
        _, ax = fig_ax
        picker = DataPicker(ax)
        picker.add_points([1, 2, 3], [4, 5, 6])
        assert len(picker.get_xy()[0]) == 3
        picker.undo()
        x, y = picker.get_xy()
        assert len(x) == 0

    def test_redo_add_batch(self, fig_ax):
        """测试重做批量添加。"""
        _, ax = fig_ax
        picker = DataPicker(ax)
        picker.add_points([1, 2, 3], [4, 5, 6])
        picker.undo()
        picker.redo()
        x, y = picker.get_xy()
        assert len(x) == 3

    def test_undo_remove_batch(self, fig_ax):
        """测试撤销批量删除。"""
        _, ax = fig_ax
        picker = DataPicker(ax, initial_points=([1, 2, 3], [4, 5, 6]))
        picker.remove_points([1, 3], [4, 6])
        assert len(picker.get_xy()[0]) == 1
        picker.undo()
        x, y = picker.get_xy()
        assert len(x) == 3

    def test_undo_clear(self, fig_ax):
        """测试撤销清空操作。"""
        _, ax = fig_ax
        picker = DataPicker(ax, initial_points=([1, 2, 3], [4, 5, 6]))
        picker.clear()
        picker.undo()
        x, y = picker.get_xy()
        assert len(x) == 3

    def test_redo_clear(self, fig_ax):
        """测试重做清空操作。"""
        _, ax = fig_ax
        picker = DataPicker(ax, initial_points=([1, 2, 3], [4, 5, 6]))
        picker.clear()
        picker.undo()
        picker.redo()
        x, y = picker.get_xy()
        assert len(x) == 0


class TestFitterWithInitialPoints:
    """测试初始点与拟合功能的集成。"""

    def test_set_fitter_fits_existing_points(self, fig_ax):
        """测试 set_fitter 对已有点触发拟合。"""
        _, ax = fig_ax
        picker = DataPicker(ax, initial_points=(
            [0, 1, 2, 3], [1, 2, 3, 4]
        ))

        def linear(x, a, b):
            return a * x + b

        picker.set_fitter(linear, min_points=3)
        fit_result = picker.namespace.get('fit_result')
        assert fit_result is not None
        # 线性拟合 y = x + 1，参数应接近 (1, 1)
        params = fit_result['params']
        assert abs(params[0] - 1.0) < 0.1
        assert abs(params[1] - 1.0) < 0.1

    def test_set_fitter_no_fit_if_insufficient_points(self, fig_ax):
        """测试点数不足时不触发拟合。"""
        _, ax = fig_ax
        picker = DataPicker(ax, initial_points=([0, 1], [1, 2]))

        def linear(x, a, b):
            return a * x + b

        picker.set_fitter(linear, min_points=3)
        fit_result = picker.namespace.get('fit_result')
        assert fit_result is None

    def test_add_points_triggers_fit(self, fig_ax):
        """测试后续 add_points 触发拟合。"""
        _, ax = fig_ax
        picker = DataPicker(ax, initial_points=([0, 1], [1, 2]))

        def linear(x, a, b):
            return a * x + b

        picker.set_fitter(linear, min_points=3)
        assert picker.namespace.get('fit_result') is None

        picker.add_points([2], [3])
        fit_result = picker.namespace.get('fit_result')
        assert fit_result is not None
