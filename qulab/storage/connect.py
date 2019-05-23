from mongoengine.connection import connect, disconnect

from qulab._config import config

__connected = False


def _connect_db():
    global __connected
    if __connected:
        return
    connect(**config['db'])
    __connected = True


def _disconnect_db():
    global __connected
    if __connected:
        disconnect()
        __connected = False


def connect_db():
    _connect_db()


def require_db(func):
    @functools.wraps(func)
    def wrapper(*args, **kwds):
        _connect_db()
        return func(*args, **kwds)

    return wrapper
