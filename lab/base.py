import sys
import tokenize


# yapf: disable
class QuLabError(Exception): pass
class QuLabTypeError(QuLabError): pass
class QuLabRuntimeError(QuLabError): pass
# yapf: enable


class MetaHasSource(type):
    '''Metaclass for all types that have attribute `__source__` and `__DBDocument__`
    '''

    def __new__(cls, name, bases, nmspc):
        return super(MetaHasSource, cls).__new__(cls, name, bases, nmspc)

    def __init__(cls, name, bases, nmspc):
        super(MetaHasSource, cls).__init__(name, bases, nmspc)
        if cls.__module__ != 'builtins':
            try:
                cls.__source__ = cls._getSourceCode()
            except:
                cls.__source__ = ''

    def _getSourceCode(cls):
        '''Get the source code of Class so we can record it into database.'''
        module = sys.modules[cls.__module__]
        if module.__name__ == '__main__' and hasattr(module, 'In'):
            code = module.In[-1]
        elif cls.__DBDocument__ is not None:
            try:
                code = cls.__DBDocument__.source
            except:
                raise QuLabTypeError('Document %r has no attribute `source`')
        elif hasattr(module, '__file__'):
            with tokenize.open(module.__file__) as f:
                code = f.read()
        else:
            code = ''
        return code


class HasSource(metaclass=MetaHasSource):
    """Base class that have attribute `__source__` and `__DBDocument__`"""
    @classmethod
    def show(cls):
        """Show source code of class."""
        from .ui import display_source_code
        display_source_code(cls.__source__)
