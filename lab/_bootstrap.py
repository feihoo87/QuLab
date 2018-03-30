# -*- coding: utf-8 -*-
import datetime
import functools
import os
import platform
import sys
import tokenize
from concurrent.futures import ProcessPoolExecutor

from mongoengine.connection import connect, disconnect

from . import _importer, db, ui
from .config import config

__run_mode = 'release'
__connected = False


if platform.system() != 'Windows':
    p_executor = None #ProcessPoolExecutor()
else:
    p_executor = None


def _connect_db():
    global __run_mode, __connected
    if __connected:
        return
    db_config = 'db_%s' % __run_mode
    if db_config in config.keys():
        connect(**config[db_config])
    else:
        connect(**config['db'])
    __connected = True
    _importer.install_meta()


def _disconnect_db():
    global __connected
    if __connected:
        disconnect()
        __connected = False
    _importer.remove_meta()


def connect_db():
    _connect_db()


def set_mode(mode):
    global __run_mode
    _disconnect_db()
    __run_mode = mode


def require_db_connection(func):
    @functools.wraps(func)
    def wrapper(*args, **kwds):
        _connect_db()
        return func(*args, **kwds)

    return wrapper


def authenticated(func):
    @functools.wraps(func)
    def wrapper(*args, **kwds):
        if get_current_user() is None:
            raise Exception('please login first')
        return func(*args, **kwds)

    return wrapper


__login_info = dict(username='', password='', user=None)


@require_db_connection
def login(username=None, password='', relogin=False):
    # if aready login
    if __login_info['user'] is not None and not relogin:
        return
    if username is None:
        username, password = ui.get_login_info()
    user = db.query.getUserByName(name=username)
    if user is not None and user.check_password(password):
        __login_info['user'] = user
        __login_info['username'] = username
        __login_info['password'] = password
    else:
        raise Exception('login fault')


def logout():
    global __login_info
    __login_info = dict(username='', password='', user=None)


def get_current_user():
    return __login_info['user']


__current_notebook = db.schema.Notebook()


def get_current_notebook():
    return __current_notebook


def get_inputCells():
    if hasattr(sys.modules['__main__'], 'In'):
        return sys.modules['__main__'].In
    else:
        return ['']


@authenticated
def save_inputCells():
    notebook = get_current_notebook()
    notebook.author = get_current_user()
    aready_saved = len(notebook.inputCells)
    for cell in get_inputCells()[aready_saved + 1:]:
        notebook.inputCells.append(
            db.update.makeUniqueCodeSnippet(cell, get_current_user()))
    notebook.save()


__inst_mgr = None


def open_instrument_mgr():
    from .device.client import InstrumentManager
    global __inst_mgr
    __inst_mgr = InstrumentManager(
        verify=config['ca_cert'])


def open_resource(name, host=None, timeout=10):
    if __inst_mgr is None:
        open_instrument_mgr()
    return __inst_mgr.open_resource(name, host=host, timeout=timeout)


def listApps(package=''):
    ret = db.query.listApplication(package=package)
    ui.listApps(ret)


def listDrivers():
    ret = db.schema.Driver.objects.order_by('name')
    ui.list_drivers(ret)


def listInstruments():
    ret = db.schema.Instrument.objects.order_by('name')
    ui.list_instruments(ret)
