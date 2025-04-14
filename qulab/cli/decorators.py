import asyncio
import functools
import inspect


def async_command(func=None):
    """
    Decorator to mark a function as an asynchronous command.
    """
    if func is None:
        return async_command

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return run(func, *args, **kwargs)

    return wrapper


def run(main, *args, **kwds):
    if inspect.iscoroutinefunction(main):
        try:
            import uvloop
            uvloop.run(main(*args, **kwds))
        except ImportError:
            asyncio.run(main(*args, **kwds))
    else:
        main(*args, **kwds)
