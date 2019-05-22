import inspect


def _parse_frame(frame):
    ret = {}
    ret['source'] = inspect.getsource(frame)
    ret['name'] = frame.f_code.co_name
    if ret['name'] != '<module>':
        argnames = frame.f_code.co_varnames[:frame.f_code.co_argcount +
                                            frame.f_code.co_kwonlyargcount]
        ret['name'] += '(' + ', '.join(argnames) + ')'
        ret['firstlineno'] = frame.f_code.co_firstlineno
    else:
        ret['firstlineno'] = 1
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


def _format_traceback(err):
    lines = []
    for frame in _parse_traceback(err):
        lines.append(f"{frame['filename']} in {frame['name']}")
        for n, line in enumerate(frame['source'].split('\n')):
            lno = n + frame['firstlineno']
            lines.append(
                f"{'->' if lno==frame['lineno'] else '  '}{lno:3d} {line}")
    traceback_text = '\n'.join(lines)
    args = list(err.args)
    args.append(traceback_text)
    err.args = tuple(args)
    return err


class QuLabException(Exception):
    """
    Base exception.
    """


###############################################################
# RPC Exceptions
###############################################################


class QuLabRPCError(QuLabException):
    """
    RPC base exception.
    """


class QuLabRPCServerError(QuLabRPCError):
    """
    Server side error.
    """

    @classmethod
    def make(cls, exce):
        exce = _format_traceback(exce)
        args = [exce.__class__.__name__]
        args.extend(list(exce.args))
        return cls(*args)


class QuLabRPCTimeout(QuLabRPCError):
    """
    Timeout.
    """


###############################################################
# DHT Exceptions
###############################################################


class QuLabDHTMalformedMessage(QuLabException):
    """
    Message does not contain what is expected.
    """
