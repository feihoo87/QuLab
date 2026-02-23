"""
QuLab Monitor Main Window Module

This module implements the main window interface for the QuLab monitor application.
It provides a scrollable grid layout of plots with configurable columns and
interactive features like axis linking and data transformation.
"""

from multiprocessing import Queue
from typing import Literal, cast

from .config import ROLL_INDICES, STYLE, TRANSFORMS
from .dataset import Dataset
from .event_queue import EventQueue
from .ploter import PlotWidget
from .qt_compat import QtCore  # type: ignore
from .qt_compat import QtWidgets  # type: ignore
from .qt_compat import (BottomDockWidgetArea, ScrollBarAlwaysOff,
                        ScrollBarAlwaysOn, TopDockWidgetArea)
from .toolbar import ToolBar


class MainWindow(QtWidgets.QMainWindow):
    """
    Main window for the QuLab monitor application.

    This window manages a grid of plot widgets and provides controls for data
    visualization and interaction. It includes features like:
    - Configurable number of columns in the plot grid
    - Scrollable plot area
    - Toolbar with plot controls
    - Real-time data updates
    - Axis linking between plots
    - Data transformation options

    Args:
        queue: Multiprocessing queue for receiving data and commands
        num_columns: Number of columns in the plot grid
        plot_minimum_height: Minimum height for each plot widget
        plot_colors: List of RGB color tuples for plot lines
    """

    def __init__(self,
                 queue: Queue,
                 num_columns: int = 3,
                 plot_minimum_height: int = 350,
                 plot_colors: list[tuple[int, int, int]] | None = None):
        super().__init__()
        self.num_columns = num_columns
        self.needs_reshuffle = False
        self.plot_minimum_height = plot_minimum_height
        self.plot_widgets: list[PlotWidget] = []
        self.plot_colors = plot_colors

        # Initialize components
        self.toolbar = ToolBar()
        self.trace_data_box = Dataset()
        self.point_data_box = Dataset()
        self.queue = EventQueue(queue, self.toolbar, self.point_data_box,
                                self.trace_data_box)

        self.init_ui()

        # Set up update timer
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(250)  # Update every 250ms

    def init_ui(self):
        """Initialize the user interface components."""
        self.setStyleSheet(STYLE)
        self.setMinimumHeight(500)
        self.setMinimumWidth(700)

        # Create scroll area
        self.scroll = QtWidgets.QScrollArea()
        self.widget = QtWidgets.QWidget()
        self.layout = QtWidgets.QGridLayout()
        self.widget.setLayout(self.layout)

        # Configure scroll area
        self.scroll.setVerticalScrollBarPolicy(ScrollBarAlwaysOn)
        self.scroll.setHorizontalScrollBarPolicy(ScrollBarAlwaysOff)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.widget)
        self.setCentralWidget(self.scroll)

        # Set up toolbar dock widget
        self.dock = QtWidgets.QDockWidget(self)
        self.dock.setAllowedAreas(TopDockWidgetArea | BottomDockWidgetArea)
        self.addDockWidget(TopDockWidgetArea, self.dock)
        self.dock.setFloating(False)
        self.dock.setWidget(self.toolbar)
        self.dock.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable)

        self.setWindowTitle('QuLab Monitor')
        self.show()
        self.toolbar.set_mainwindow(self)
        self.toolbar.pb.setChecked(True)

    @property
    def mode(self) -> Literal["P", "T"]:
        """Current plotting mode (Points or Traces)."""
        return cast(Literal["P", "T"], self.toolbar.mode)

    @property
    def dataset(self) -> Dataset:
        """Current active dataset based on mode."""
        return {"P": self.point_data_box, "T": self.trace_data_box}[self.mode]

    def set_num_columns(self, columns: int):
        """Set the number of columns in the plot grid."""
        columns = max(1, min(10, int(columns)))
        if columns != self.num_columns:
            self.needs_reshuffle = True
            self.num_columns = columns

    def add_subplot(self) -> PlotWidget:
        """Add a new plot widget to the grid."""
        plot_count = len(self.plot_widgets)
        plot_widget = PlotWidget(self.plot_minimum_height, self.plot_colors)
        self.plot_widgets.append(plot_widget)

        grid_row = plot_count // self.num_columns
        grid_col = plot_count % self.num_columns
        self.layout.addWidget(plot_widget, grid_row + 1, grid_col)
        return plot_widget

    def create_subplots(self, xy_pairs: list[tuple[str, str]]):
        """Create multiple subplots with given X-Y axis pairs."""
        for x_name, y_name in xy_pairs:
            plot_widget = self.add_subplot()
            plot_widget.set_x_label(x_name)
            plot_widget.set_y_label(y_name)
        self.do_link()
        self.all_enable_auto_range()

    def clear_subplots(self):
        """Remove all plot widgets from the grid."""
        for plot_widget in self.plot_widgets:
            self.layout.removeWidget(plot_widget)
            plot_widget.setParent(None)
        self.plot_widgets.clear()

    def remove_plot(self, widget: PlotWidget):
        """Remove a specific plot widget from the grid."""
        widget.setParent(None)
        self.plot_widgets.remove(widget)
        self.reshuffle()

    def drop_last_plot(self, index: int = -1):
        """Remove the plot at the specified index."""
        index = int(index)
        if index < len(self.plot_widgets):
            widget = self.plot_widgets[index]
            widget.setParent(None)
            del widget
            del self.plot_widgets[index]
        self.reshuffle()

    def reshuffle(self):
        """Rearrange plot widgets in the grid."""
        for idx, widget in enumerate(self.plot_widgets):
            widget.setParent(None)
            grid_row = idx // self.num_columns
            grid_col = idx % self.num_columns
            self.layout.addWidget(widget, grid_row + 1, grid_col)

    def keyPressEvent(self, event):
        """Handle keyboard events for column adjustment."""
        key = event.text()
        if key in ['_', '-']:
            self.set_num_columns(self.num_columns - 1)
        elif key in ['=', '+']:
            self.set_num_columns(self.num_columns + 1)

    def do_link(self):
        """Link plots that share the same X or Y axis."""
        same_x_axis: dict[str, list[int]] = {}
        xy_pairs = self.toolbar.xypairs

        # Group plots by X axis
        for idx, (x_name, _) in enumerate(xy_pairs):
            if x_name not in same_x_axis:
                same_x_axis[x_name] = []
            same_x_axis[x_name].append(idx)

        share_x, share_y = self.toolbar.sharexy()
        should_unlink = not (share_x and share_y)

        # Link or unlink axes
        for x_name, plot_indices in same_x_axis.items():
            prev_idx = -1
            for curr_idx in plot_indices:
                if prev_idx != -1:
                    if should_unlink:
                        self.plot_widgets[prev_idx].plotItem.vb.setXLink(None)
                        self.plot_widgets[prev_idx].plotItem.vb.setYLink(None)

                    if share_x:
                        self.plot_widgets[prev_idx].plotItem.vb.setXLink(
                            self.plot_widgets[curr_idx].plotItem.vb)

                    if share_y:
                        self.plot_widgets[prev_idx].plotItem.vb.setYLink(
                            self.plot_widgets[curr_idx].plotItem.vb)
                prev_idx = curr_idx

    def all_auto_range(self):
        """Auto-range all plot widgets."""
        for plot_widget in self.plot_widgets:
            plot_widget.auto_range()

    def all_enable_auto_range(self):
        """Enable auto-range for all plot widgets."""
        for plot_widget in self.plot_widgets:
            plot_widget.enable_auto_range()

    def update(self):
        """Update plots with new data and handle UI changes."""
        self.queue.flush()
        needs_rescale = False

        # Handle plot layout changes
        if self.toolbar.xypairs_dirty:
            self.clear_subplots()
            self.create_subplots(self.toolbar.xypairs)
            self.toolbar.xypairs_dirty = False
            needs_rescale = True

        if self.toolbar.link_dirty:
            self.do_link()
            self.toolbar.link_dirty = False

        if self.needs_reshuffle:
            self.needs_reshuffle = False
            self.reshuffle()

        # Update plot settings
        if self.toolbar.xyfm_dirty:
            for plot_widget in self.plot_widgets:
                plot_widget.plotItem.ctrl.logXCheck.setChecked(self.toolbar.lx)
                plot_widget.plotItem.ctrl.logYCheck.setChecked(self.toolbar.ly)

        # Handle data updates
        if self.toolbar.CR_flag:
            self.toolbar.CR_flag = False
            self.dataset.clear_history()
            self.dataset.dirty = True

        if self.dataset.dirty or self.toolbar.xyfm_dirty or needs_rescale:
            self.dataset.dirty = False
            self.toolbar.xyfm_dirty = False

            # Update plot data
            for plot_widget in self.plot_widgets:
                x_transform = TRANSFORMS[cast(str, self.toolbar.fx)]
                y_transform = TRANSFORMS[cast(str, self.toolbar.fy)]

                for idx in ROLL_INDICES:
                    x_data, y_data = self.dataset.get_data(
                        idx, plot_widget.x_name, plot_widget.y_name)
                    data_length = min(len(x_data), len(y_data))
                    x_data = x_transform(x_data[:data_length], 0)
                    y_data = y_transform(y_data[:data_length], 0)
                    plot_widget.set_data(idx, x_data, y_data)

                plot_widget.update()
                if needs_rescale:
                    plot_widget.auto_range()
