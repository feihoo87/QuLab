from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QApplication

class ActionGroupBox(QtWidgets.QGroupBox):
    def __init__(self, parent=None):
        super(ActionGroupBox, self).__init__('Actions', parent=parent)
        layout = QtWidgets.QHBoxLayout(self)

        self.start_btn = QtWidgets.QPushButton("Start", parent=self)
        self.stop_btn = QtWidgets.QPushButton("Stop", parent=self)
        self.stop_btn.setEnabled(False)

        layout.addWidget(self.start_btn)
        layout.addWidget(self.stop_btn)

        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)

    @QtCore.pyqtSlot()
    def start(self):
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    @QtCore.pyqtSlot()
    def stop(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)


class InstruentServerMainWindow(QtWidgets.QMainWindow):
    on_start = QtCore.pyqtSignal()
    on_stop = QtCore.pyqtSignal()

    def __init__(self, server):
        super(InstruentServerMainWindow, self).__init__()
        self.initUI()
        self.server = server

    def initUI(self):
        self.centralwidget = QtWidgets.QWidget(self)
        self.layout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.actions = ActionGroupBox()
        self.layout.addWidget(self.actions)
        self.setCentralWidget(self.centralwidget)
        self.setWindowTitle(u'Hello (QuLab v0.1)')
        self.actions.start_btn.clicked.connect(self.start)
        self.actions.stop_btn.clicked.connect(self.stop)

    @QtCore.pyqtSlot()
    def start(self):
        self.server.start()
        self.on_start.emit()

    @QtCore.pyqtSlot()
    def stop(self):
        self.server.stop()
        self.on_stop.emit()
