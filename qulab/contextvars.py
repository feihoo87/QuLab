import collections.abc
import hashlib
import pickle
import threading

from qulab.sugar import getDHT

__all__ = ('ContextVar', 'Context', 'Token', 'copy_context', 'set_context')

_NO_DEFAULT = object()

SET = 1
DEL = 2


async def createOperate(op, pre, key, value=None):
    buff = pickle.dumps((op, pre, key, value))
    key = hashlib.sha1(buff).digest()
    dht = await getDHT()
    await dht.set_digest(key, buff)
    return key


async def getOperate(key):
    dht = await getDHT()
    buff = await dht.get_digest(key)
    return pickle.loads(buff)


class IMap:
    def __init__(self):
        self._op_id = None

    async def operate(self):
        if self._op_id is None:
            return None
        return await getOperate(self._op_id)

    async def __aiter__(self):
        op = await self.operate()
        if op is None:
            return
        deleted = None
        overwrited = None
        if op[0] == SET:
            yield op[2], op[3]
            overwrited = op[2]
        else:
            deleted = op[2]
        pre = IMap()
        pre._op_id = op[1]
        async for key, value in pre.__aiter__():
            if deleted is not None and key == deleted:
                pass
            elif overwrited is not None and key == overwrited:
                pass
            else:
                yield key, value

    async def has(self, key):
        if self._op_id is None:
            return False
        op = await self.operate()
        if op[2] == key:
            if op[0] == SET:
                return True
            else:
                return False
        else:
            pre = IMap()
            pre._op_id = op[1]
            return await pre.has(key)

    async def get(self, key, default=None):
        if self._op_id is None:
            return default
        op = await self.operate()
        if op[2] == key:
            if op[0] == SET:
                return op[3]
            else:
                return default
        else:
            pre = IMap()
            pre._op_id = op[1]
            return await pre.get(key, default)

    async def set(self, key, value):
        if await self.has(key) and value == await self.get(key):
            return self
        m = IMap()
        m._op_id = await createOperate(SET, self._op_id, key, value)
        return m

    async def delete(self, key):
        if not await self.has(key):
            return self
        m = IMap()
        m._op_id = await createOperate(DEL, self._op_id, key)
        return m


class ContextMeta(type):

    # contextvars.Context is not subclassable.

    def __new__(mcls, names, bases, dct):
        cls = super().__new__(mcls, names, bases, dct)
        if cls.__module__ != 'qulab.contextvars' or cls.__name__ != 'Context':
            raise TypeError("type 'Context' is not an acceptable base type")
        return cls


class Context(metaclass=ContextMeta):
    def __init__(self):
        self._data = IMap()
        self._name = None

    def copy(self):
        new = Context()
        new._data = self._data
        return new

    async def get(self, var):
        if not isinstance(var, ContextVar):
            raise TypeError(
                "a ContextVar key was expected, got {!r}".format(var))
        return await self._data.get(var.name)

    async def get_by_name(self, name):
        return await self._data.get(name)

    async def has(self, var):
        if not isinstance(var, ContextVar):
            raise TypeError(
                "a ContextVar key was expected, got {!r}".format(var))
        return await self._data.has(var.name)

    async def __aiter__(self):
        async for name, var in self._data:
            yield name, var

    async def save_as(self, key):
        self._name = key
        dht = await getDHT()
        await dht.set(key, self._data._op_id)

    @staticmethod
    async def load(key):
        dht = await getDHT()
        ctx = Context()
        ctx._name = key
        ctx._data._op_id = await dht.get(key)
        set_context(ctx)
        return ctx


class ContextVarMeta(type):

    # contextvars.ContextVar is not subclassable.

    def __new__(mcls, names, bases, dct):
        cls = super().__new__(mcls, names, bases, dct)
        if cls.__module__ != 'qulab.contextvars' or cls.__name__ != 'ContextVar':
            raise TypeError("type 'ContextVar' is not an acceptable base type")
        return cls

    def __getitem__(cls, name):
        return


class ContextVar(metaclass=ContextVarMeta):
    def __init__(self, name, *, default=_NO_DEFAULT):
        if not isinstance(name, str):
            raise TypeError("context variable name must be a str")
        self._name = name
        self._default = default

    @property
    def name(self):
        return self._name

    async def get(self, default=_NO_DEFAULT):
        ctx = _get_context()
        value = await ctx.get(self)
        if value is not None:
            return value

        if default is not _NO_DEFAULT:
            return default

        if self._default is not _NO_DEFAULT:
            return self._default

        raise LookupError

    async def set(self, value):
        ctx = _get_context()
        data = ctx._data
        try:
            old_value = await data.get(self)
        except KeyError:
            old_value = Token.MISSING

        updated_data = await data.set(self.name, value)
        ctx._data = updated_data
        if ctx._name is not None:
            await ctx.save_as(ctx._name)
        return Token(ctx, self, old_value)

    async def reset(self, token):
        if token._used:
            raise RuntimeError("Token has already been used once")

        if token._var is not self:
            raise ValueError("Token was created by a different ContextVar")

        if token._context is not _get_context():
            raise ValueError("Token was created in a different Context")

        ctx = token._context
        if token._old_value is Token.MISSING:
            ctx._data = await ctx._data.delete(token._var.name)
        else:
            ctx._data = await ctx._data.set(token._var.name, token._old_value)
        if ctx._name is not None:
            await ctx.save_as(ctx._name)
        token._used = True

    def __repr__(self):
        r = '<ContextVar name={!r}'.format(self.name)
        if self._default is not _NO_DEFAULT:
            r += ' default={!r}'.format(self._default)
        return r + ' at {:0x}>'.format(id(self))


class TokenMeta(type):

    # contextvars.Token is not subclassable.

    def __new__(mcls, names, bases, dct):
        cls = super().__new__(mcls, names, bases, dct)
        if cls.__module__ != 'qulab.contextvars' or cls.__name__ != 'Token':
            raise TypeError("type 'Token' is not an acceptable base type")
        return cls


class Token(metaclass=TokenMeta):

    MISSING = object()

    def __init__(self, context, var, old_value):
        self._context = context
        self._var = var
        self._old_value = old_value
        self._used = False

    @property
    def var(self):
        return self._var

    @property
    def old_value(self):
        return self._old_value

    def __repr__(self):
        r = '<Token '
        if self._used:
            r += ' used'
        r += ' var={!r} at {:0x}>'.format(self._var, id(self))
        return r


def copy_context():
    return _get_context().copy()


def _get_context():
    ctx = getattr(_state, 'context', None)
    if ctx is None:
        ctx = Context()
        _state.context = ctx
    return ctx


def set_context(ctx):
    _state.context = ctx


_state = threading.local()
