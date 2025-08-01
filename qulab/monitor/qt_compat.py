"""
QuLab Monitor Qt Compatibility Module

This module provides compatibility layer for Qt constants and enums across
different Qt bindings (PyQt5, PyQt6, PySide2, PySide6). It ensures consistent
access to Qt constants regardless of the Qt binding being used.

The module exports the following constants:
- AlignRight: Right alignment flag
- BottomDockWidgetArea: Bottom dock widget area constant
- ScrollBarAlwaysOn: Always show scrollbar policy
- ScrollBarAlwaysOff: Never show scrollbar policy
- TopDockWidgetArea: Top dock widget area constant
"""

from matplotlib.backends.qt_compat import (QT_API, QtCore,  # type: ignore
                                           QtWidgets)       # type: ignore

# Define Qt constants based on the Qt binding being used
if QT_API in ['PySide6', 'PyQt6']:
    # Qt6 uses enum flags
    AlignRight = QtCore.Qt.AlignmentFlag.AlignRight
    BottomDockWidgetArea = QtCore.Qt.DockWidgetArea.BottomDockWidgetArea
    ScrollBarAlwaysOn = QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOn
    ScrollBarAlwaysOff = QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    TopDockWidgetArea = QtCore.Qt.DockWidgetArea.TopDockWidgetArea
elif QT_API in ['PyQt5', 'PySide2']:
    # Qt5 uses direct constants
    AlignRight = QtCore.Qt.AlignRight
    BottomDockWidgetArea = QtCore.Qt.BottomDockWidgetArea
    ScrollBarAlwaysOn = QtCore.Qt.ScrollBarAlwaysOn
    ScrollBarAlwaysOff = QtCore.Qt.ScrollBarAlwaysOff
    TopDockWidgetArea = QtCore.Qt.TopDockWidgetArea
else:
    raise ValueError(f"Unsupported Qt binding: {QT_API}")

# Export all constants
__all__ = [
    'QtCore',
    'QtWidgets',
    'AlignRight',
    'BottomDockWidgetArea',
    'ScrollBarAlwaysOn',
    'ScrollBarAlwaysOff',
    'TopDockWidgetArea',
]
