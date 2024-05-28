import ast
import asyncio
import inspect
from typing import Any, Callable

from .expression import Env, Expression


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