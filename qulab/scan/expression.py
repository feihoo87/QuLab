from __future__ import annotations

import operator

import numpy as np
from pyparsing import (CaselessKeyword, Combine, Forward, Group, Keyword,
                       Literal, Optional, ParserElement, Suppress, Word,
                       alphanums, alphas, delimitedList, nums, oneOf, opAssoc,
                       pyparsing_common, restOfLine, srange, stringEnd,
                       stringStart)
from scipy import special

LPAREN, RPAREN, LBRACK, RBRACK, LBRACE, RBRACE, DOT, TILDE, BANG, PLUS, MINUS = map(
    Suppress, "()[]{}.~!+-")

INT = Combine(srange("[1-9]") +
              Optional(Word(nums))).set_parse_action(lambda t: int(t[0]))
OCT = Combine("0" + Word("01234567")).set_parse_action(lambda t: int(t[0], 8))
HEX = Combine("0x" + Word("0123456789abcdefABCDEF")).set_parse_action(
    lambda t: int(t[0], 16))
FLOAT = Combine(Word(nums) + DOT + Word(nums)) | \
        Combine(DOT + Word(nums)) | \
        Combine(Word(nums) + DOT) | \
        Combine(Word(nums) + DOT + Word(nums) + CaselessKeyword("e") + Word("+-") + Word(nums)) | \
        Combine(Word(nums) + DOT + CaselessKeyword("e") + Word("+-") + Word(nums)) | \
        Combine(DOT + Word(nums) + CaselessKeyword("e") + Word("+-") + Word(nums)) | \
        Combine(Word(nums) + CaselessKeyword("e") + Word("+-") + Word(nums))
FLOAT.set_parse_action(lambda t: float(t[0]))
SYMBOL = Word(alphas, alphanums + "_")
SYMBOL.set_parse_action(lambda t: Symbol(t[0]))

expr = Forward()
unary = Forward()
binary = Forward()
atom = Forward()

atom << (INT | OCT | HEX | FLOAT | SYMBOL | (LPAREN + expr + RPAREN) |
         (LBRACK + expr + RBRACK) | (LBRACE + expr + RBRACE) | (MINUS + atom) |
         (PLUS + atom) | (TILDE + atom) | (BANG + atom) | (nums + DOT + nums))

unary << (atom | (MINUS + unary) | (PLUS + unary) | (TILDE + unary) |
          (BANG + unary))

ConstType = (int, float, complex)
_empty = object()


class Ref():
    __slots__ = ['name']

    def __init__(self, name):
        self.name = name

    def __repr__(self) -> str:
        return f"Ref({self.name!r})"


class Env():

    def __init__(self):
        self.consts = {}
        self.variables = {}
        self.refs = {}
        self.functions = {
            'sin': np.sin,
            'cos': np.cos,
            'tan': np.tan,
            'pi': np.pi,
            'e': np.e,
            'log': np.log,
            'log2': np.log2,
            'log10': np.log10,
            'exp': np.exp,
            'sqrt': np.sqrt,
            'abs': np.abs,
            'sinh': np.sinh,
            'cosh': np.cosh,
            'tanh': np.tanh,
            'arcsin': np.arcsin,
            'arccos': np.arccos,
            'arctan': np.arctan,
            'arctan2': np.arctan2,
            'arcsinh': np.arcsinh,
            'arccosh': np.arccosh,
            'arctanh': np.arctanh,
            'sinc': np.sinc,
            'sign': np.sign,
            'heaviside': np.heaviside,
            'erf': special.erf,
            'erfc': special.erfc,
        }

    def __contains__(self, key):
        return key in self.consts or key in self.variables or key in self.functions or key in self.refs

    def __getitem__(self, key):
        if key in self.consts:
            return self.consts[key]
        if key in self.variables:
            return self.variables[key]
        if key in self.functions:
            return self.functions[key]
        if key in self.refs:
            return self[self.refs[key]]
        raise KeyError(f"Key {key} not found")

    def __setitem__(self, key, value):
        if key in self.consts:
            raise KeyError(f"Key {key:r} is const")
        elif isinstance(value, Ref):
            self.create_ref(key, value.name)
        elif key in self.refs:
            self[self.refs[key]] = value
        else:
            self.variables[key] = value

    def __delitem__(self, key):
        if key in self.consts:
            raise KeyError(f"Key {key:r} is const")
        elif key in self.refs:
            del self[self.refs[key]]
        else:
            del self.variables[key]

    def ref(self, key):
        if key in self:
            return Ref(key)
        else:
            raise KeyError(f"Key {key!r} not found")

    def create_ref(self, key, name):
        if name in self.refs:
            if key in self.refs[name]:
                raise ValueError(f"Key {key!r} already exists in ref {name!r}")
            else:
                self.refs[key] = [name, *self.refs[name]]
        else:
            self.refs[key] = [name]

    def is_const(self, key):
        return key in self.consts


_default_env = Env()


class Expression():

    def __init__(self):
        self.cache = _empty

    def d(self, x: str | Symbol):
        if isinstance(x, Symbol):
            x = x.name
        if x in self.symbols():
            return self.derivative(x)
        else:
            return 0

    def derivative(self, x):
        raise NotImplementedError

    def __add__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        if isinstance(other, ConstType) and other == 0:
            return self
        return BinaryExpression(self, other, operator.add)

    def __radd__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        if isinstance(other, ConstType) and other == 0:
            return self
        return BinaryExpression(other, self, operator.add)

    def __sub__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        if isinstance(other, ConstType) and other == 0:
            return self
        return BinaryExpression(self, other, operator.sub)

    def __rsub__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        if isinstance(other, ConstType) and other == 0:
            return -self
        return BinaryExpression(other, self, operator.sub)

    def __mul__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        if isinstance(other, ConstType) and other == 0:
            return 0
        if isinstance(other, ConstType) and other == 1:
            return self
        if isinstance(other, ConstType) and other == -1:
            return -self
        return BinaryExpression(self, other, operator.mul)

    def __rmul__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        if isinstance(other, ConstType) and other == 0:
            return 0
        if isinstance(other, ConstType) and other == 1:
            return self
        if isinstance(other, ConstType) and other == -1:
            return -self
        return BinaryExpression(other, self, operator.mul)

    def __matmul__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return BinaryExpression(self, other, operator.matmul)

    def __rmatmul__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return BinaryExpression(other, self, operator.matmul)

    def __truediv__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        if isinstance(other, ConstType) and other == 1:
            return self
        if isinstance(other, ConstType) and other == -1:
            return -self
        return BinaryExpression(self, other, operator.truediv)

    def __rtruediv__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        if isinstance(other, ConstType) and other == 0:
            return 0
        return BinaryExpression(other, self, operator.truediv)

    def __floordiv__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        if isinstance(other, ConstType) and other == 1:
            return self
        if isinstance(other, ConstType) and other == -1:
            return -self
        return BinaryExpression(self, other, operator.floordiv)

    def __rfloordiv__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        if isinstance(other, ConstType) and other == 0:
            return 0
        return BinaryExpression(other, self, operator.floordiv)

    def __mod__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        if isinstance(other, ConstType) and other == 1:
            return 0
        return BinaryExpression(self, other, operator.mod)

    def __rmod__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return BinaryExpression(other, self, operator.mod)

    def __pow__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        if isinstance(other, ConstType) and other == 0:
            return 1
        if isinstance(other, ConstType) and other == 1:
            return self
        return BinaryExpression(self, other, operator.pow)

    def __rpow__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        if isinstance(other, ConstType) and other == 0:
            return 0
        return BinaryExpression(other, self, operator.pow)

    def __neg__(self):
        return UnaryExpression(self, operator.neg)

    def __pos__(self):
        return UnaryExpression(self, operator.pos)

    def __abs__(self):
        return UnaryExpression(self, operator.abs)

    def __not__(self):
        return UnaryExpression(self, operator.not_)

    def __inv__(self):
        return UnaryExpression(self, operator.inv)

    def __invert__(self):
        return UnaryExpression(self, operator.invert)

    def __index__(self):
        return UnaryExpression(self, operator.index)

    def __eq__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return BinaryExpression(self, other, operator.eq)

    def __ne__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return BinaryExpression(self, other, operator.ne)

    def __lt__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return BinaryExpression(self, other, operator.lt)

    def __le__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return BinaryExpression(self, other, operator.le)

    def __gt__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return BinaryExpression(self, other, operator.gt)

    def __ge__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return BinaryExpression(self, other, operator.ge)

    def __and__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return BinaryExpression(self, other, operator.and_)

    def __rand__(self, other):
        if isinstance(other, Expression):
            other
        return BinaryExpression(other, self, operator.and_)

    def __or__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return BinaryExpression(self, other, operator.or_)

    def __ror__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return BinaryExpression(other, self, operator.or_)

    def __lshift__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return BinaryExpression(self, other, operator.lshift)

    def __rlshift__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return BinaryExpression(other, self, operator.lshift)

    def __rshift__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return BinaryExpression(self, other, operator.rshift)

    def __rrshift__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return BinaryExpression(other, self, operator.rshift)

    def __xor__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return BinaryExpression(self, other, operator.xor)

    def __rxor__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return BinaryExpression(other, self, operator.xor)

    def __getitem__(self, other):
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return ObjectMethod(self, '__getitem__', other)

    def __getattr__(self, other):
        if isinstance(other, str):
            if other.startswith('_') or other in self.__dict__:
                return super().__getattr__(other)
        if isinstance(other, Expression):
            other = other.eval(_default_env)
        return ObjectMethod(self, '__getattr__', other)

    def __call__(self, *args):
        args = [
            o.eval(_default_env) if isinstance(o, Expression) else o
            for o in args
        ]
        return ObjectMethod(self, '__call__', *args)

    def __round__(self, n=None):
        return self

    def __bool__(self):
        return True

    def eval(self, env):
        raise NotImplementedError

    def symbols(self) -> list[str]:
        raise NotImplementedError

    def changed(self, env) -> bool:
        return True

    def is_const(self, env) -> bool:
        return False

    def value(self, env=_default_env):
        if isinstance(env, dict):
            e = Env()
            e.variables = env
            env = e
        if self.changed(env):
            self.cache = self.eval(env)
        return self.cache


class UnaryExpression(Expression):

    def __init__(self, a, op):
        super().__init__()
        self.a = a
        self.op = op

    def __getstate__(self) -> dict:
        return {'a': self.a, 'op': self.op}

    def __setstate__(self, state: dict):
        self.a = state['a']
        self.op = state['op']
        self.cache = _empty

    def symbols(self) -> list[str]:
        if isinstance(self.a, Expression):
            return self.a.symbols()
        else:
            return []

    def changed(self, env) -> bool:
        if isinstance(self.a, ConstType):
            return False
        return self.cache is _empty or isinstance(
            self.a, Expression) and self.a.changed(env)

    def is_const(self, env) -> bool:
        return isinstance(self.a,
                          Expression) and self.a.is_const(env) or isinstance(
                              self.a, ConstType)

    def eval(self, env):
        a = self.a.value(env) if isinstance(self.a, Expression) else self.a
        return self.op(a)

    def derivative(self, x):
        if isinstance(self.a, Expression):
            return self.op(self.a.d(x))
        else:
            return 0

    def __repr__(self) -> str:
        return f"{self.op.__name__}({self.a!r})"


class BinaryExpression(Expression):

    def __init__(self, a, b, op):
        super().__init__()
        self.a = a
        self.b = b
        self.op = op

    def __getstate__(self) -> dict:
        return {'a': self.a, 'b': self.b, 'op': self.op}

    def __setstate__(self, state: dict):
        self.a = state['a']
        self.b = state['b']
        self.op = state['op']
        self.cache = _empty

    def symbols(self) -> list[str]:
        symbs = set()
        if isinstance(self.a, Expression):
            symbs.update(self.a.symbols())
        if isinstance(self.b, Expression):
            symbs.update(self.b.symbols())
        return list(symbs)

    def eval(self, env):
        a = self.a.value(env) if isinstance(self.a, Expression) else self.a
        b = self.b.value(env) if isinstance(self.b, Expression) else self.b
        return self.op(a, b)

    def derivative(self, x):
        if isinstance(self.a, Expression):
            da = self.a.d(x)
        else:
            da = 0
        if isinstance(self.b, Expression):
            db = self.b.d(x)
        else:
            db = 0

        if self.op is operator.add:
            return da + db
        elif self.op is operator.sub:
            return da - db
        elif self.op is operator.mul:
            return self.a * db + da * self.b
        elif self.op is operator.truediv:
            return (da * self.b - self.a * db) / self.b**2
        elif self.op is operator.pow:
            if isinstance(self.a, Expression) and isinstance(
                    self.b, Expression):
                return self.a**self.b * (self.b * da / self.a +
                                         ObjectMethod(np, 'log', self.a) * db)
            elif isinstance(self.a, Expression):
                return self.b * self.a**(self.b - 1) * da
            elif isinstance(self.b, Expression):
                return np.log(self.a) * db * self.a**self.b
            else:
                return 0
        else:
            return 0

    def __repr__(self) -> str:
        return f"({self.a!r} {self.op.__name__} {self.b!r})"


class ObjectMethod(Expression):

    def __init__(self, obj, method: str, *args):
        super().__init__()
        self.obj = obj
        self.method = method
        self.args = args

    def __getstate__(self) -> dict:
        return {'obj': self.obj, 'method': self.method, 'args': self.args}

    def __setstate__(self, state: dict):
        self.obj = state['obj']
        self.method = state['method']
        self.args = state['args']
        self.cache = _empty

    def symbols(self) -> list[str]:
        symbs = set()
        if isinstance(self.obj, Expression):
            symbs.update(self.obj.symbols())
        for a in self.args:
            if isinstance(a, Expression):
                symbs.update(a.symbols())
        return list(symbs)

    def eval(self, env):
        obj = self.obj.value(env) if isinstance(self.obj,
                                                Expression) else self.obj
        args = [
            a.value(env) if isinstance(a, Expression) else a for a in self.args
        ]
        if isinstance(obj, Expression) or any(
                isinstance(x, Expression) for x in args):
            return ObjectMethod(obj, self.method, *args)
        else:
            return getattr(obj, self.method)(*args)

    def __repr__(self):
        if self.method == '__call__':
            return f"{self.obj!r}({', '.join(map(repr, self.args))})"
        else:
            return f"{self.obj!r}.{self.method}({', '.join(map(repr, self.args))})"


class Symbol(Expression):

    def __init__(self, name):
        super().__init__()
        self.name = name

    def __getstate__(self) -> dict:
        return {'name': self.name}

    def __setstate__(self, state: dict):
        self.name = state['name']
        self.cache = _empty

    def symbols(self) -> list[str]:
        return [self.name]

    def eval(self, env):
        if self.name in env:
            return env[self.name]
        else:
            return self

    def derivative(self, x):
        if x == self.name:
            return 1
        else:
            return 0

    def __repr__(self) -> str:
        return self.name


sin = Symbol('sin')
cos = Symbol('cos')
tan = Symbol('tan')
pi = Symbol('pi')
e = Symbol('e')
log = Symbol('log')
log2 = Symbol('log2')
log10 = Symbol('log10')
exp = Symbol('exp')
sqrt = Symbol('sqrt')
abs = Symbol('abs')
sinh = Symbol('sinh')
cosh = Symbol('cosh')
tanh = Symbol('tanh')
arcsin = Symbol('arcsin')
arccos = Symbol('arccos')
arctan = Symbol('arctan')
arctan2 = Symbol('arctan2')
arcsinh = Symbol('arcsinh')
arccosh = Symbol('arccosh')
arctanh = Symbol('arctanh')
sinc = Symbol('sinc')
sign = Symbol('sign')
heaviside = Symbol('heaviside')
erf = Symbol('erf')
erfc = Symbol('erfc')
