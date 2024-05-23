import inspect
from concurrent.futures import Future


def call_func_with_kwds(func, args, kwds, log=None):
    funcname = getattr(func, '__name__', repr(func))
    sig = inspect.signature(func)
    for p in sig.parameters.values():
        if p.kind == p.VAR_KEYWORD:
            return func(*args, **kwds)
    kw = {
        k: v
        for k, v in kwds.items()
        if k in list(sig.parameters.keys())[len(args):]
    }
    try:
        args = [
            arg.result() if isinstance(arg, Future) else arg for arg in args
        ]
        kw = {
            k: v.result() if isinstance(v, Future) else v
            for k, v in kw.items()
        }
        return func(*args, **kw)
    except:
        if log:
            log.exception(f'Call {funcname} with {args} and {kw}')
        raise
    finally:
        if log:
            log.debug(f'Call {funcname} with {args} and {kw}')


def try_to_call(x, args, kwds, log=None):
    if callable(x):
        return call_func_with_kwds(x, args, kwds, log)
    return x
