import inspect


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

