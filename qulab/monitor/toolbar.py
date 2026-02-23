"""
QuLab Monitor Toolbar Module

This module implements the toolbar interface for the QuLab monitor application.
The toolbar provides controls for:
- Switching between point and trace data modes
- Configuring plot formats and transformations
- Managing axis linking and scaling
- Controlling auto-range and data clearing
"""

import itertools
import re
from typing import Callable, List, Tuple

from .config import STYLE
from .qt_compat import AlignRight, QtWidgets  # type: ignore


def matched_xy_pairs(patterns: str, column_names: list[str]) -> list[tuple[str, str]]:
    """
    Find matching X-Y column pairs based on pattern strings.

    Args:
        patterns: Semicolon-separated patterns for matching column pairs
        column_names: List of available column names

    Returns:
        List of matched (x, y) column name pairs
    """
    pattern_list = patterns.replace(" ", "").split(";")
    pairs = []
    for x, y in itertools.product(column_names, repeat=2):
        test = f"{x},{y}"
        for pattern in pattern_list:
            r = re.match(pattern, test)
            if r and r.group(0) == test:
                pairs.append((x, y))
                break
    return pairs


class FormatCombo(QtWidgets.QComboBox):
    """Base class for format selection combo boxes."""

    def __init__(self):
        super().__init__()
        self.on_change_callable = None

    def set_on_change_event_action(self, callback: Callable[[], None]) -> None:
        """Set the callback function for when the selection changes."""
        self.on_change_callable = callback
        self.activated.connect(callback)

    def set_idx(self, idx: int) -> None:
        """Set the current index and trigger the change callback."""
        self.setCurrentIndex(idx)
        if callable(self.on_change_callable):
            self.on_change_callable()


class XFormatCombo(FormatCombo):
    """Combo box for X-axis data transformation selection."""

    def __init__(self):
        super().__init__()
        for transform in ["real", "imag", "mag", "phase"]:
            self.addItem(transform)


class YFormatCombo(FormatCombo):
    """Combo box for Y-axis data transformation selection."""

    def __init__(self):
        super().__init__()
        for transform in ["mag", "phase", "real", "imag"]:
            self.addItem(transform)


class LineEdit(QtWidgets.QLineEdit):
    """Custom line edit with change event support."""

    def set_on_change_event_action(self, callback: Callable[[], None]) -> None:
        """Set the callback function for when editing is finished."""
        self.on_change_callable = callback
        self.editingFinished.connect(callback)

    def set_text(self, text: str) -> None:
        """Set the text and trigger the change callback."""
        self.setText(text)
        if callable(self.on_change_callable):
            self.on_change_callable()


class SelectionBundle:
    """
    Bundle of UI controls for plot configuration.
    
    This class groups together the controls for:
    - X-Y pair selection
    - Data transformations
    - Axis scaling
    - Axis linking
    """

    def __init__(self):
        # Plot configuration controls
        self.stx = LineEdit()  # X-Y pair selection text
        self.fx = XFormatCombo()  # X-axis transformation
        self.fy = YFormatCombo()  # Y-axis transformation
        self.lx = QtWidgets.QCheckBox("logX")  # X-axis log scale
        self.ly = QtWidgets.QCheckBox("logY")  # Y-axis log scale
        self.linkx = QtWidgets.QCheckBox("ShareX")  # X-axis linking
        self.linky = QtWidgets.QCheckBox("ShareY")  # Y-axis linking

    def set_on_change_event_actions(self, on_text_edited: Callable[[], None],
                                  on_format_changed: Callable[[], None],
                                  on_log_scale_marker_changed: Callable[[], None]) -> None:
        """Set callback functions for various control changes."""
        self.stx.set_on_change_event_action(on_text_edited)
        self.fx.set_on_change_event_action(on_format_changed)
        self.fy.set_on_change_event_action(on_format_changed)
        self.lx.toggled.connect(on_format_changed)
        self.ly.toggled.connect(on_format_changed)
        self.linkx.toggled.connect(on_log_scale_marker_changed)
        self.linky.toggled.connect(on_log_scale_marker_changed)

    def remove_from_layout(self) -> None:
        """Remove all controls from their parent layout."""
        for widget in [self.stx, self.fx, self.fy, self.lx, self.ly,
                      self.linkx, self.linky]:
            widget.setParent(None)

    def add_to_layout(self, layout: QtWidgets.QGridLayout) -> None:
        """Add all controls to the specified layout."""
        # Column positions for controls
        layout.addWidget(self.stx, 0, 3)
        layout.addWidget(self.fx, 0, 5)
        layout.addWidget(self.fy, 0, 7)
        layout.addWidget(self.lx, 0, 10)
        layout.addWidget(self.ly, 0, 11)
        layout.addWidget(self.linkx, 0, 12)
        layout.addWidget(self.linky, 0, 13)


class ToolBar(QtWidgets.QWidget):
    """
    Main toolbar widget for the monitor application.

    This widget provides controls for:
    - Switching between point and trace data modes
    - Configuring plot formats and transformations
    - Managing axis linking and scaling
    - Controlling auto-range and data clearing
    """

    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLE)

        # Mode selection
        self.mode = 'P'  # 'P' for points, 'T' for traces
        self.pb = QtWidgets.QRadioButton('Points')
        self.tb = QtWidgets.QRadioButton('Traces')
        self.pb.setChecked(True)
        self.pb.toggled.connect(self.toggle_mode)
        self.tb.toggled.connect(self.toggle_mode)

        # Labels
        self.ytxt_lb = QtWidgets.QLabel("(X,Y)")
        self.fx_lb = QtWidgets.QLabel("fx")
        self.fy_lb = QtWidgets.QLabel("fy")
        self.ytxt_lb.setAlignment(AlignRight)
        self.fx_lb.setAlignment(AlignRight)
        self.fy_lb.setAlignment(AlignRight)

        # Selection bundles for points and traces
        self.ps = SelectionBundle()
        self.ts = SelectionBundle()
        self.ps.set_on_change_event_actions(
            self.text_edited, self.generate_transform, self.link_edited)
        self.ts.set_on_change_event_actions(
            self.text_edited, self.generate_transform, self.link_edited)

        # State flags
        self.xypairs: List[Tuple[str, str]] = []
        self.xypairs_dirty = True
        self.fx = None
        self.fy = None
        self.xyfm_dirty = True
        self.link_dirty = True
        self.lx = False
        self.ly = False
        self.CR_flag = False

        # Layout setup
        self.layout = QtWidgets.QGridLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

        # Add basic controls
        self.layout.addWidget(self.pb, 0, 0)
        self.layout.addWidget(self.tb, 0, 1)
        self.layout.addWidget(self.ytxt_lb, 0, 2)
        self.layout.addWidget(self.fx_lb, 0, 4)
        self.layout.addWidget(self.fy_lb, 0, 6)

        # Add action buttons
        self.AR = QtWidgets.QPushButton("AR")
        self.CR = QtWidgets.QPushButton("CLR")
        self.AR.setMaximumWidth(30)
        self.CR.setMaximumWidth(30)
        self.AR.setToolTip("Auto Range")
        self.CR.setToolTip("Clear History Plots")
        self.layout.addWidget(self.AR, 0, 8)
        self.layout.addWidget(self.CR, 0, 9)

        self.refresh_layout()

    @property
    def column_names(self) -> list[str]:
        """Get column names for the current mode."""
        return {
            "P": self.mainwindow.point_data_box.column_names,
            "T": self.mainwindow.trace_data_box.column_names
        }[self.mode]

    @property
    def selections(self) -> SelectionBundle:
        """Get the selection bundle for the current mode."""
        return {"P": self.ps, "T": self.ts}[self.mode]

    def set_trace_text(self, text: str) -> None:
        """Set the X-Y pair text for trace mode."""
        self.ts.stx.set_text(text)

    def set_point_text(self, text: str) -> None:
        """Set the X-Y pair text for point mode."""
        self.ps.stx.set_text(text)

    def sharexy(self) -> tuple[bool, bool]:
        """Get the current axis sharing state."""
        return (self.selections.linkx.isChecked(),
                self.selections.linky.isChecked())

    def set_mainwindow(self, mainwindow) -> None:
        """Connect the toolbar to the main window."""
        self.mainwindow = mainwindow
        self.AR.clicked.connect(self.mainwindow.all_enable_auto_range)
        self.CR.clicked.connect(self.clear_history)

    def clear_history(self) -> None:
        """Set flag to clear plot history."""
        self.CR_flag = True

    def refresh_layout(self) -> None:
        """Update the layout based on current mode."""
        if self.mode == 'P':
            self.ts.remove_from_layout()
            self.ps.add_to_layout(self.layout)
        elif self.mode == 'T':
            self.ps.remove_from_layout()
            self.ts.add_to_layout(self.layout)

    def toggle_mode(self) -> None:
        """Handle mode toggle between points and traces."""
        self.mode = 'P' if self.pb.isChecked() else 'T'
        self.refresh_layout()
        self.refresh_comb()

    def refresh_comb(self) -> None:
        """Refresh all combo boxes and update tooltips."""
        self.generate_transform()
        self.text_edited()
        self.ytxt_lb.setToolTip(str(self.column_names))

    def link_edited(self) -> None:
        """Handle changes to axis linking."""
        self.link_dirty = True

    def generate_transform(self) -> None:
        """Update transformation settings."""
        self.fx = self.selections.fx.currentText()
        self.fy = self.selections.fy.currentText()
        self.lx = self.selections.lx.isChecked()
        self.ly = self.selections.ly.isChecked()
        self.xyfm_dirty = True

    def text_edited(self) -> None:
        """Handle changes to X-Y pair text."""
        text = self.selections.stx.text()
        if not text:
            self.xypairs = []
        else:
            self.xypairs = matched_xy_pairs(text, self.column_names)
        self.xypairs_dirty = True
