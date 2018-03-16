# -*- coding: utf-8 -*-
import base64
import threading

import tornado.ioloop
import tornado.web
import tornado.websocket
from PyQt5 import QtCore, QtWidgets
from tornado import httpserver

from ..config import config as cfg
from ..device.client import InstrumentManager
from ..device.protocol import DEFAULT_PORT, Transport
from .handlers import *


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


def make_app(config):
    settings = config.get('web_settings')
    instr_mgr = InstrumentManager(
        verify=None, hosts=config.get('server_name'))
    trans = Transport()
    initialize_options = dict(instr_mgr=instr_mgr, trans=trans)

    return tornado.web.Application([
        (r"/", MainHandler, initialize_options),
        (r"/login", LoginHandler, initialize_options),
        (r"/logout", LogoutHandler, initialize_options),
        (r"/api/inst/(?P<inst>\w+)", OpenInstrumentHandler, initialize_options),
        (r"/api/inst/(?P<inst>\w+)/(?P<method>\w+)", PerformMethodHandler, initialize_options),
    ], **settings)


class InstrumentServer:
    def __init__(self, config, port=DEFAULT_PORT, ssl_options=None):
        self.app = make_app(config)
        self.server = httpserver.HTTPServer(self.app, ssl_options=ssl_options)
        self.server.listen(port)
        self._IOloop = tornado.ioloop.IOLoop.current()

    def run_for_ever(self):
        self._IOloop.start()

    def start(self):
        self._thread = threading.Thread(target=self.run_for_ever)
        self._thread.start()

    def stop(self):
        self._IOloop.stop()


def main():
    import sys
    import ssl
    import os
    from PyQt5.QtWidgets import QApplication
    from lab._bootstrap import connect_db

    cookie_secret = base64.urlsafe_b64encode(ssl.RAND_bytes(32)).decode()

    config = {
        'web_settings': {
            'cookie_secret': cookie_secret
        },
        'visa_backends': cfg['visa_backends'],
    }

    ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_ctx.load_cert_chain(cfg['ssl']['cert'], cfg['ssl']['key'])

    app = QApplication(sys.argv)
    connect_db()
    server = InstrumentServer(
        config=config,
        port=cfg.get('server_port', DEFAULT_PORT),
        ssl_options=ssl_ctx)
    win = InstruentServerMainWindow(server)
    win.show()
    # server.run_for_ever()
    sys.exit(app.exec_())
