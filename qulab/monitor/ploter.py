"""
QuLab Monitor Plotter Module

This module provides a custom plotting widget based on pyqtgraph for real-time
data visualization. It includes features like auto-ranging, mouse interaction
for data selection, and clipboard integration.
"""

from .config import (COLOR_SELECTED, COLOR_UNSELECTED, DEFAULT_COLORS,
                     LINE_WIDTHS, ROLL_INDICES, SYMBOL_SIZES)
from .qt_compat import QtWidgets  # type: ignore

# the plotting widget
try:
    import pyqtgraph as pg  # type: ignore
except ImportError:
    raise ImportError("Please install pyqtgraph first")

try:
    import pyperclip as pc  # type: ignore
    HAS_CLIPBOARD = True
except ImportError:
    HAS_CLIPBOARD = False


class PlotWidget(pg.PlotWidget):
    """
    Custom plotting widget extending pyqtgraph's PlotWidget.

    This widget provides additional features like:
    - Configurable plot colors and styles
    - Mouse interaction for data point selection
    - Clipboard integration for selected data points
    - Auto-ranging and axis control

    Args:
        minimum_height: Minimum height of the plot widget in pixels
        colors: List of RGB color tuples for plot lines
    """

    def __init__(self, minimum_height=300, colors=None):
        self.x_axis_linked = False
        self.y_axis_linked = False
        if colors is None:
            colors = DEFAULT_COLORS
        elif len(colors) < len(DEFAULT_COLORS):
            colors.extend(DEFAULT_COLORS[len(colors):])
        self.colors = colors
        self.x_name = ""
        self.y_name = ""
        super().__init__()

        self.setMinimumHeight(minimum_height)
        self.showGrid(x=True, y=True)
        self.setBackground(COLOR_UNSELECTED)

        self.plotItem.vb.autoRange()

        ## Labeling
        self.x_label = QtWidgets.QLabel(self)
        self.x_label.setText("X:")
        self.x_label.move(0, 5)
        self.y_label = QtWidgets.QLabel(self)
        self.y_label.setText("Y:")
        self.y_label.move(0, 35)

        self.plots = {}
        self.clip_pos_start = 0
        self.clip_pos_end = 0
        self.range_select = False
        for idx in ROLL_INDICES:
            self.plots[idx] = \
              self.plot([],[] ,pen={"color":self.colors[idx]  ,"width":LINE_WIDTHS[idx]} ,
                  symbolBrush = self.colors[idx],
                  symbolPen = { "width":0 ,"color":self.colors[idx] }   ,
                  symbolSize =SYMBOL_SIZES[idx] ,
              )
        self.update()

    def set_x_label(self, label: str) -> None:
        """Set the X-axis label."""
        self.x_name = label
        self.x_label.setText(f"X:{label}")

    def set_y_label(self, label: str) -> None:
        """Set the Y-axis label."""
        self.y_name = label
        self.y_label.setText(f"Y:{label}")

    def auto_range(self) -> None:
        """Automatically adjust plot range to show all data."""
        self.plotItem.vb.autoRange()

    def enable_auto_range(self) -> None:
        """Enable automatic range adjustment."""
        self.plotItem.vb.enableAutoRange()

    def keyPressEvent(self, event):
        """Handle keyboard events for plot control.
        
        Keys:
            F/f: Auto-range the plot
            A/a: Enable auto-pan
            R/r: Enable range selection mode
        """
        key = event.text().lower()
        if key == 'f':
            self.plotItem.vb.autoRange()
        elif key == 'a':
            self.plotItem.vb.setAutoPan()
        elif key == 'r':
            self.range_select = True
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Handle key release events."""
        key = event.text().lower()
        if key == 'r':
            self.range_select = False
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse press events for data selection."""
        if event.button() == 4 and HAS_CLIPBOARD:
            self.clip_pos_start = self.plotItem.vb.mapSceneToView(
                event.pos()).x()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release events and copy selected data to clipboard."""
        if event.button() == 4 and HAS_CLIPBOARD:
            self.clip_pos_end = self.plotItem.vb.mapSceneToView(
                event.pos()).x()
            if self.range_select:
                pc.copy(f"{self.clip_pos_start},{self.clip_pos_end}")
            else:
                pc.copy(str(self.clip_pos_end))
        else:
            super().mouseReleaseEvent(event)

    def update(self):
        super().update()

    def set_data(self, index: int, x_data, y_data) -> None:
        """Update plot data for the specified index."""
        self.plots[index].setData(x_data, y_data)

    # def mouseDoubleClickEvent(self, ev):
    #     super().mouseDoubleClickEvent(ev)
