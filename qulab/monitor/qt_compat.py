from matplotlib.backends.qt_compat import QT_API, QtCore, QtWidgets

if QT_API in ['PySide6', 'PyQt6']:
    AlignRight = QtCore.Qt.AlignmentFlag.AlignRight
    BottomDockWidgetArea = QtCore.Qt.DockWidgetArea.BottomDockWidgetArea
    ScrollBarAlwaysOn = QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOn
    ScrollBarAlwaysOff = QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    TopDockWidgetArea = QtCore.Qt.DockWidgetArea.TopDockWidgetArea
elif QT_API in ['PyQt5', 'PySide2']:
    AlignRight = QtCore.Qt.AlignRight
    BottomDockWidgetArea = QtCore.Qt.BottomDockWidgetArea
    ScrollBarAlwaysOn = QtCore.Qt.ScrollBarAlwaysOn
    ScrollBarAlwaysOff = QtCore.Qt.ScrollBarAlwaysOff
    TopDockWidgetArea = QtCore.Qt.TopDockWidgetArea
else:
    raise AssertionError(f"Unexpected QT_API: {QT_API}")
