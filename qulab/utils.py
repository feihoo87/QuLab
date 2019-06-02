# -*- coding: utf-8 -*-
import contextlib
import functools
import inspect
import os
import socket
import struct
import time
import uuid
from functools import wraps
from hashlib import sha1

import numpy as np


def IEEE_488_2_BinBlock(datalist, dtype="int16", is_big_endian=True):
    """
    将一组数据打包成 IEEE 488.2 标准二进制块

    Args:
        datalist : 要打包的数字列表
        dtype    : 数据类型
        endian   : 字节序

    Returns:
        binblock, header
        二进制块, 以及其 'header'
    """
    types = {"b"      : (  int, 'b'), "B"      : (  int, 'B'),
             "h"      : (  int, 'h'), "H"      : (  int, 'H'),
             "i"      : (  int, 'i'), "I"      : (  int, 'I'),
             "q"      : (  int, 'q'), "Q"      : (  int, 'Q'),
             "f"      : (float, 'f'), "d"      : (float, 'd'),
             "int8"   : (  int, 'b'), "uint8"  : (  int, 'B'),
             "int16"  : (  int, 'h'), "uint16" : (  int, 'H'),
             "int32"  : (  int, 'i'), "uint32" : (  int, 'I'),
             "int64"  : (  int, 'q'), "uint64" : (  int, 'Q'),
             "float"  : (float, 'f'), "double" : (float, 'd'),
             "float32": (float, 'f'), "float64": (float, 'd')
    } # yapf: disable

    datalist = np.asarray(datalist)
    datalist.astype(types[dtype][0])
    if is_big_endian:
        endianc = '>'
    else:
        endianc = '<'
    datablock = struct.pack(
        '%s%d%s' % (endianc, len(datalist), types[dtype][1]), *datalist)
    size = '%d' % len(datablock)
    header = '#%d%s' % (len(size), size)

    return header.encode() + datablock, header


@functools.lru_cache(maxsize=1)
def getHostIP():
    """
    获取本机 ip 地址
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except OSError:
        return '127.0.0.1'
    finally:
        s.close()
    return ip


@functools.lru_cache(maxsize=1)
def getHostIPv6():
    """
    获取本机 ipv6 地址
    """
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        s.connect(('2001:4860:4860::8888', 80, 0, 0))
        ip = s.getsockname()[0]
    except OSError:
        return '::1'
    finally:
        s.close()
    return ip


@functools.lru_cache(maxsize=1)
def getHostMac():
    """
    获取本机 mac 地址
    """
    mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
    return ":".join([mac[e:e + 2] for e in range(0, 11, 2)])


def randomID():
    """
    Generate a random msg ID.
    """
    msgID = sha1(os.urandom(32)).digest()
    return msgID


def acceptArg(f, name, keyword=True):
    """
    Test if argument is acceptable by function.

    Args:
        f: callable
            function
        name: str
            argument name
    """
    sig = inspect.signature(f)
    for param in sig.parameters.values():
        if param.name == name and param.kind != param.VAR_POSITIONAL:
            return True
        elif param.kind == param.VAR_KEYWORD:
            return True
        elif param.kind == param.VAR_POSITIONAL and not keyword:
            return True
    return False


def retry(exception_to_check, tries=4, delay=0.5, backoff=2, logger=None):
    """Retry calling the decorated function using an exponential backoff.
    Args:
        exception_to_check (Exception): the exception to check.
                                        may be a tuple of exceptions to check
        tries (int): number of times to try (not retry) before giving up
        delay (float, int): initial delay between retries in seconds
        backoff (int): backoff multiplier e.g. value of 2 will double the delay
                       each retry
        logger (logging.Logger): logger to use. If None, print
    """

    def deco_retry(func):
        @wraps(func)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return func(*args, **kwargs)
                except exception_to_check as exc:
                    msg = "%s, Retrying in %s seconds..." % (str(exc), mdelay)
                    if logger:
                        logger.warning(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return func(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry


@contextlib.contextmanager
def _WindowsShutdownBlocker(title='Python script'):
    """
    Block Windows shutdown when you do something important.
    """
    from ctypes import CFUNCTYPE, c_bool, c_uint, c_void_p, c_wchar_p, windll
    import win32con
    import win32gui

    def WndProc(hWnd, message, wParam, lParam):
        if message == win32con.WM_QUERYENDSESSION:
            return False
        else:
            return win32gui.DefWindowProc(hWnd, message, wParam, lParam)

    CALLBACK = CFUNCTYPE(c_bool, c_void_p, c_uint, c_void_p, c_void_p)

    wc = win32gui.WNDCLASS()
    wc.style = win32con.CS_GLOBALCLASS | win32con.CS_VREDRAW | win32con.CS_HREDRAW
    wc.lpfnWndProc = CALLBACK(WndProc)
    wc.hbrBackground = win32con.COLOR_WINDOW + 1
    wc.lpszClassName = "block_shutdown_class"
    win32gui.RegisterClass(wc)

    hwnd = win32gui.CreateWindow(wc.lpszClassName, title,
                                 win32con.WS_OVERLAPPEDWINDOW, 50,
                                 50, 100, 100, 0, 0,
                                 win32gui.GetForegroundWindow(), None)

    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)

    windll.user32.ShutdownBlockReasonCreate.argtypes = [c_void_p, c_wchar_p]
    windll.user32.ShutdownBlockReasonCreate.restype = c_bool
    windll.user32.ShutdownBlockReasonCreate(
        hwnd, "Important work in processing, don't shutdown :-(")

    yield

    windll.user32.ShutdownBlockReasonDestroy.argtypes = [c_void_p]
    windll.user32.ShutdownBlockReasonDestroy.restype = c_bool
    windll.user32.ShutdownBlockReasonDestroy(hwnd)
    win32gui.DestroyWindow(hwnd)
    win32gui.UnregisterClass(wc.lpszClassName, None)


@contextlib.contextmanager
def _FakeShutdownBlocker(title='Python script'):
    yield


if os.name == 'nt':
    ShutdownBlocker = _WindowsShutdownBlocker
else:
    ShutdownBlocker = _FakeShutdownBlocker
