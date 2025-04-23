import ast
import asyncio
import inspect
import platform
import re
import subprocess
import sys
import uuid
import warnings
from typing import Any, Callable

import dill

from ..expression import Env, Expression


class Unpicklable:

    def __init__(self, obj):
        self.type = str(type(obj))
        self.id = id(obj)

    def __repr__(self):
        return f'<Unpicklable: {self.type} at 0x{id(self):x}>'


class TooLarge:

    def __init__(self, obj):
        self.type = str(type(obj))
        self.id = id(obj)

    def __repr__(self):
        return f'<TooLarge: {self.type} at 0x{id(self):x}>'


def dump_dict(d, keys=[]):
    ret = {}

    for key, value in d.items():
        if key in keys:
            ret[key] = value
            continue
        if isinstance(value, dict) and isinstance(key, str):
            ret[key] = dump_dict(value,
                                 keys=[
                                     k[len(key) + 1:] for k in keys
                                     if k.startswith(f'{key}.')
                                 ])
        else:
            try:
                ret[key] = dill.dumps(value)
            except:
                ret[key] = Unpicklable(value)

    return dill.dumps(ret)


def load_dict(buff):
    if isinstance(buff, dict):
        return {key: load_dict(value) for key, value in buff.items()}

    if not isinstance(buff, bytes):
        return buff

    try:
        ret = dill.loads(buff)
    except:
        return buff

    if isinstance(ret, dict):
        return load_dict(ret)
    else:
        return ret


def dump_globals(ns=None, *, size_limit=10 * 1024 * 1024, warn=False):
    import __main__

    if ns is None:
        ns = __main__.__dict__

    namespace = {}

    for name, value in ns.items():
        try:
            buf = dill.dumps(value)
        except:
            namespace[name] = Unpicklable(value)
            if warn:
                warnings.warn(f'Unpicklable: {name} {type(value)}')
        if len(buf) > size_limit:
            namespace[name] = TooLarge(value)
            if warn:
                warnings.warn(f'TooLarge: {name} {type(value)}')
        else:
            namespace[name] = buf

    return namespace


def is_valid_identifier(s: str) -> bool:
    """
    Check if a string is a valid identifier.
    """
    try:
        ast.parse(f"f({s}=0)")
        return True
    except SyntaxError:
        return False


async def async_next(aiter):
    try:
        if hasattr(aiter, '__anext__'):
            return await aiter.__anext__()
        else:
            return next(aiter)
    except StopIteration:
        raise StopAsyncIteration from None


async def async_zip(*aiters):
    aiters = [
        ait.__aiter__() if hasattr(ait, '__aiter__') else iter(ait)
        for ait in aiters
    ]
    try:
        while True:
            # 使用 asyncio.gather 等待所有异步生成器返回下一个元素
            result = await asyncio.gather(*(async_next(ait) for ait in aiters))
            yield tuple(result)
    except StopAsyncIteration:
        # 当任一异步生成器耗尽时停止迭代
        return


async def call_function(func: Callable | Expression, variables: dict[str,
                                                                     Any]):
    if isinstance(func, Expression):
        env = Env()
        for name in func.symbols():
            if name in variables:
                if inspect.isawaitable(variables[name]):
                    variables[name] = await variables[name]
                env.variables[name] = variables[name]
            else:
                raise ValueError(f'{name} is not provided.')
        return func.eval(env)

    try:
        sig = inspect.signature(func)
    except:
        return func()
    args = []
    for name, param in sig.parameters.items():
        if param.kind == param.POSITIONAL_OR_KEYWORD:
            if name in variables:
                if inspect.isawaitable(variables[name]):
                    variables[name] = await variables[name]
                args.append(variables[name])
            elif param.default is not param.empty:
                args.append(param.default)
            else:
                raise ValueError(f'parameter {name} is not provided.')
        elif param.kind == param.VAR_POSITIONAL:
            raise ValueError('not support VAR_POSITIONAL')
        elif param.kind == param.VAR_KEYWORD:
            ret = func(**variables)
            if inspect.isawaitable(ret):
                ret = await ret
            return ret
    ret = func(*args)
    if inspect.isawaitable(ret):
        ret = await ret
    return ret


def yapf_reformat(cell_text):
    try:
        import isort
        import yapf.yapflib.yapf_api

        fname = f"f{uuid.uuid1().hex}"

        def wrap(source):
            lines = [f"async def {fname}():"]
            for line in source.split('\n'):
                lines.append("    " + line)
            return '\n'.join(lines)

        def unwrap(source):
            lines = []
            for line in source.split('\n'):
                if line.startswith(f"async def {fname}():"):
                    continue
                lines.append(line[4:])
            return '\n'.join(lines)

        cell_text = re.sub('^%', '#%#', cell_text, flags=re.M)
        try:
            reformated_text = yapf.yapflib.yapf_api.FormatCode(
                isort.code(cell_text))[0]
        except:
            reformated_text = unwrap(
                yapf.yapflib.yapf_api.FormatCode(wrap(
                    isort.code(cell_text)))[0])
        return re.sub('^#%#', '%', reformated_text, flags=re.M)
    except:
        return cell_text


def get_installed_packages():
    result = subprocess.run([sys.executable, '-m', 'pip', 'freeze'],
                            stdout=subprocess.PIPE,
                            text=True)

    lines = result.stdout.split('\n')
    packages = []
    for line in lines:
        if line:
            packages.append(line)
    return packages


def get_system_info():
    info = {
        'OS': platform.uname()._asdict(),
        'Python': sys.version,
        'PythonExecutable': sys.executable,
        'PythonPath': sys.path,
        'packages': get_installed_packages()
    }
    return info
