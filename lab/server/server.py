# -*- coding: utf-8 -*-
import base64
import threading

import tornado.ioloop
import tornado.web
import tornado.websocket
from tornado import httpserver

from ..config import config as cfg
from ..device.client import InstrumentManager
from ..device.protocol import DEFAULT_PORT, Transport
from .handlers import *


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
    import ssl
    import os
    from lab._bootstrap import connect_db

    cookie_secret = base64.urlsafe_b64encode(ssl.RAND_bytes(32)).decode()

    config = {
        'web_settings': {
            'cookie_secret': cookie_secret
        },
        'server_name': cfg['server_name'],
        'visa_backends': cfg['visa_backends'],
    }

    ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_ctx.load_cert_chain(cfg['ssl']['cert'], cfg['ssl']['key'])

    connect_db()
    server = InstrumentServer(
        config=config,
        port=cfg.get('server_port', DEFAULT_PORT),
        ssl_options=ssl_ctx)
    try:
        from . import ui
        import sys
        app = ui.QtWidgets.QApplication(sys.argv)
        win = ui.InstruentServerMainWindow(server)
        win.show()
        sys.exit(app.exec_())
    except:
        server.run_for_ever()
