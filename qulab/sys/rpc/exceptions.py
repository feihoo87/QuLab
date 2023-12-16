import inspect
from collections import deque


def _parse_frame(frame):
    ret = {}
    ret['source'] = inspect.getsource(frame)
    ret['name'] = frame.f_code.co_name
    ret['firstlineno'] = 1
    if ret['name'] != '<module>':
        argnames = frame.f_code.co_varnames[:frame.f_code.co_argcount +
                                            frame.f_code.co_kwonlyargcount]
        ret['name'] += '(' + ', '.join(argnames) + ')'
        ret['firstlineno'] = frame.f_code.co_firstlineno
    ret['filename'] = frame.f_code.co_filename
    return ret


def _parse_traceback(err):
    ret = []
    tb = err.__traceback__
    while tb is not None:
        frame = _parse_frame(tb.tb_frame)
        frame['lineno'] = tb.tb_lineno
        ret.append(frame)
        tb = tb.tb_next
    return ret


def _format_frame(frame):
    post_lines = -1
    lines = deque(maxlen=16)
    lines.append(f"{frame['filename']} in {frame['name']}")
    for n, line in enumerate(frame['source'].split('\n')):
        lno = n + frame['firstlineno']
        if lno == frame['lineno']:
            lines.append(f"->{lno:3d} {line}")
            post_lines = 0
        else:
            lines.append(f"  {lno:3d} {line}")
            if post_lines >= 0:
                post_lines += 1
        if post_lines >= 7:
            break
    return '\n'.join(lines)


def _format_traceback(err):
    frame_text = []
    for frame in _parse_traceback(err):
        frame_text.append(_format_frame(frame))
    traceback_text = '\n'.join(frame_text)
    args = list(err.args)
    args.append(traceback_text)
    err.args = tuple(args)
    return err


###############################################################
# RPC Exceptions
###############################################################


class RPCError(Exception):
    """
    RPC base exception.
    """


class RPCServerError(RPCError):
    """
    Server side error.
    """

    @classmethod
    def make(cls, exce):
        exce = _format_traceback(exce)
        args = [exce.__class__.__name__]
        args.extend(list(exce.args))
        return cls(*args)

    def _repr_markdown_(self):
        return '\n'.join([
            '```python',
            '---------------------------------------------------------------------------',
            f'RPCServerError({self.args[0]})               Server raise:{self.args[1]}',
            f'{self.args[2]}',
            '---------------------------------------------------------------------------',
            '```',
        ])


class RPCTimeout(RPCError):
    """
    Timeout.
    """
