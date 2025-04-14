import copy
import itertools
import logging
import re
import string
from collections import defaultdict
from functools import partial
from typing import Any, Callable, Literal, NamedTuple

log = logging.getLogger(__name__)

Decorator = Callable[[Callable], Callable]

_buildin_set = set


class Source():
    pass


class Sink():
    pass


def action(key: str,
           method: Literal['get', 'set', 'post', 'delete'] = 'get',
           **kwds) -> Decorator:

    if any(c in key for c in ",()[]<>"):
        raise ValueError('Invalid key: ' + key)

    def decorator(func):
        func.__action__ = key, method, kwds
        return func

    return decorator


def get(key: str, **kwds) -> Decorator:
    return action(key, 'get', **kwds)


def set(key: str, **kwds) -> Decorator:
    return action(key, 'set', **kwds)


def post(key: str, **kwds) -> Decorator:
    return action(key, 'post', **kwds)


def delete(key: str, **kwds) -> Decorator:
    return action(key, 'delete', **kwds)


class _Exclusion(NamedTuple):
    keys: list


def exclude(sections: list):
    return _Exclusion(sections)


def _add_action(attrs: dict, key: str, method: str, func: Callable, doc: dict,
                sections: dict) -> None:
    try:
        mapping = attrs[f'__{method}_actions__']
    except KeyError:
        raise ValueError('Invalid method: ' + method)
    arguments = re.findall(r'\{(\w+)\}', key)
    doc[method][key] = func.__doc__
    matrix = {}
    for arg in arguments:
        if (arg not in attrs and arg not in sections or arg in sections
                and arg not in attrs and isinstance(sections[arg], _Exclusion)
                or arg in sections and arg in attrs
                and isinstance(sections[arg], _Exclusion) and len(
                    _buildin_set(attrs[arg]) -
                    _buildin_set(sections[arg].keys)) == 0):
            raise ValueError(
                f'Undefined section: {arg!r} in @action({key!r}, {method!r})')
        if arg in sections and not isinstance(sections[arg], _Exclusion):
            matrix[arg] = sections[arg]
        else:
            if arg in sections:
                matrix[arg] = [
                    k for k in attrs[arg] if k not in sections[arg].keys
                ]
            else:
                matrix[arg] = attrs[arg]
    for values in itertools.product(*[matrix[arg] for arg in arguments]):
        kwds = dict(zip(arguments, values))
        # mapping[key.format(**kwds)] = partial(func, **kwds)
        mapping[string.Template(key).substitute(kwds)] = partial(func, **kwds)


def _build_docs(mapping: dict, attrs: dict) -> str:
    docs = []
    for key, doc in mapping.items():
        if not doc:
            doc = "No documentation."
        docs.append(f"key = \"{key}\"")
        lines = doc.strip().split('\n')
        docs.extend(lines)
        docs.append("")
    return '\n'.join(docs)


class DeviceMeta(type):

    def __new__(cls, name, bases, attrs):
        doc = defaultdict(dict)
        for method in ['get', 'set', 'post', 'delete']:
            attrs.setdefault(f'__{method}_actions__', {})
        for attr in attrs.values():
            if hasattr(attr, '__action__'):
                key, method, kwds = attr.__action__
                _add_action(attrs, key, method, attr, doc, kwds)
        new_class = super().__new__(cls, name, bases, attrs)

        for method in ['get', 'set', 'post', 'delete']:
            getattr(new_class,
                    method).__doc__ = f"{method.upper()}\n\n" + _build_docs(
                        doc[method], attrs)
        return new_class


class BaseDevice(metaclass=DeviceMeta):
    __log__ = None

    def __init__(self, address: str = None, **options):
        self._state = {}
        self._status = "NOT CONNECTED"
        self.address = address
        self.options = options

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    @property
    def log(self):
        if self.__log__ is None:
            self.__log__ = logging.getLogger(
                f"{self.__class__.__module__}.{self.__class__.__name__}")
        return self.__log__

    @property
    def state(self):
        return copy.deepcopy(self._state)
    
    def get_state(self, key: str, default=None) -> Any:
        return self._state.get(key, default)

    @property
    def status(self):
        return self._status

    def open(self) -> None:
        self._status = "CONNECTED"

    def close(self) -> None:
        self._status = "NOT CONNECTED"
        self._state.clear()

    def reset(self) -> None:
        self._state.clear()

    def get(self, key: str, default: Any = None) -> Any:
        self.log.info(f'Get {key!r}')
        if key in self.__get_actions__:
            result = self.__get_actions__[key](self)
            self._state[key] = result
            return result
        else:
            return self._state.get(key, default)

    def set(self, key: str, value: Any = None) -> None:
        self.log.info(f'Set {key!r} = {value!r}')
        self.__set_actions__[key](self, value)
        self._state[key] = value

    def post(self, key: str, value: Any = None) -> Any:
        self.log.info(f'Post {key!r} = {value!r}')
        return self.__post_actions__[key](self, value)

    def delete(self, key: str) -> None:
        self.log.info(f'Delete {key!r}')
        self.__delete_actions__[key](self)
        del self._state[key]

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.address!r})'


class VisaDevice(BaseDevice):

    error_query = 'SYST:ERR?'

    def open(self) -> None:
        import pyvisa
        kwds = self.options.copy()
        if 'backend' in kwds:
            rm = pyvisa.ResourceManager(kwds.pop('backend'))
        else:
            rm = pyvisa.ResourceManager()
        self.resource = rm.open_resource(self.address, **kwds)
        self.errors = []
        super().open()

    def close(self) -> None:
        super().close()
        self.resource.close()

    def reset(self) -> None:
        super().reset()
        self.resource.write('*RST')

    def check_error(self):
        if self.error_query:
            while True:
                error = self.resource.query(self.error_query)
                error_code = int(error.split(',')[0])
                if error_code == 0:
                    break
                self.errors.append(error)

    @get('idn')
    def get_idn(self) -> str:
        """Get instrument identification."""
        return self.resource.query('*IDN?')

    @get('opc')
    def get_opc(self) -> bool:
        """Get operation complete."""
        return bool(int(self.resource.query('*OPC?')))

    @get('errors')
    def get_errors(self) -> list[str]:
        """Get error queue."""
        self.check_error()
        errors = self.errors
        self.errors = []
        return errors

    @set('timeout')
    def set_timeout(self, value: float) -> None:
        """Set timeout in seconds."""
        self.resource.timeout = round(value * 1000)

    @get('timeout')
    def get_timeout(self) -> float:
        """Get timeout in seconds."""
        return self.resource.timeout / 1000
