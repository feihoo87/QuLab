import functools

from mongoengine.connection import connect as _connect
from mongoengine.connection import disconnect as _disconnect

from qulab._config import config

__connection = None


def connect():
    global __connection
    if __connection is not None:
        return
    uri = config['db']['mongodb']
    __connection = _connect(host=uri)


def disconnect():
    global __connection
    if __connection is not None:
        _disconnect()
        __connection = None


def get_connection():
    connect()
    return __connection


def require_db(func):
    @functools.wraps(func)
    def wrapper(*args, **kwds):
        connect()
        return func(*args, **kwds)

    return wrapper
