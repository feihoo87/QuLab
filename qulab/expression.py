from __future__ import annotations

import operator

import numpy as np
from pyparsing import (CaselessKeyword, Combine, Forward, Group, Keyword,
                       Literal, MatchFirst, Optional, ParserElement,
                       ParseResults, Regex, Suppress, Word, ZeroOrMore,
                       alphanums, alphas, delimitedList, infixNotation, nums,
                       oneOf, opAssoc, pyparsing_common, restOfLine, srange,
                       stringEnd, stringStart)
from scipy import special

# 启用 Packrat 优化以提高解析效率
ParserElement.enablePackrat()

# 定义符号（括号、方括号、花括号、点号等）的 Suppress 版
LPAREN, RPAREN = map(Suppress, "()")
LBRACK, RBRACK = map(Suppress, "[]")
LBRACE, RBRACE = map(Suppress, "{}")
DOT = Suppress(".")
COMMA = Suppress(",")

# 数字定义：整数（十进制、八进制、十六进制）和浮点数
INT = (Combine(Word("123456789", nums))
       | Literal("0")).setParseAction(lambda t: int(t[0]))
OCT = Combine("0" + Word("01234567")).setParseAction(lambda t: int(t[0], 8))
HEX = Combine("0x" + Word("0123456789abcdefABCDEF")).setParseAction(
    lambda t: int(t[0], 16))
FLOAT = Combine(
    Word(nums) + '.' + Word(nums) | '.' + Word(nums) | Word(nums) + '.'
    | Word(nums) + (Literal('e') | Literal('E')) +
    Word("+-" + nums)).setParseAction(lambda t: float(t[0]))


# 定义标识符，转换为 Symbol 对象（在 Expression 类中已定义）
def symbol_parse_action(t):
    return Symbol(t[0])


SYMBOL = Word(alphas + "_",
              alphanums + "_").setParseAction(symbol_parse_action)


# 定义查询语法：$a.b.c 或 $a.b 或 $a
def query_parse_action(t):
    return Query(t[0])


attr_chain = ZeroOrMore(Combine(Literal('.') + SYMBOL))
dollar_named_chain = Combine(Literal('$') + SYMBOL + attr_chain)
dollar_dotN_chain = Combine(
    Literal('$') + Regex(r'\.{1,}') + SYMBOL + attr_chain)
dollar_simple = Combine(Literal('$') + SYMBOL)

QUERY = MatchFirst([dollar_dotN_chain, dollar_named_chain,
                    dollar_simple]).setParseAction(lambda s, l, t: Query(t[0]))

#------------------------------------------------------------------------------
# 定义运算表达式的解析动作转换函数

# 一元运算符映射（注意：此处 ! 使用逻辑非 operator.not_）
unary_ops = {
    '+': operator.pos,
    '-': operator.neg,
    '~': operator.invert,
    '!': operator.not_
}


def unary_parse_action(tokens: ParseResults) -> Expression:
    # tokens 形如：[['-', operand]]
    op, operand = tokens[0]
    # operand 已经是 Expression 对象（或常量），构造 UnaryExpression
    return UnaryExpression(operand, unary_ops[op])


# 二元运算符映射
binary_ops = {
    '+': operator.add,
    '-': operator.sub,
    '*': operator.mul,
    '/': operator.truediv,
    '//': operator.floordiv,
    '%': operator.mod,
    '**': operator.pow,
    '@': operator.matmul,
    '<<': operator.lshift,
    '>>': operator.rshift,
    '&': operator.and_,
    '^': operator.xor,
    '|': operator.or_,
    '<': operator.lt,
    '<=': operator.le,
    '>': operator.gt,
    '>=': operator.ge,
    '==': operator.eq,
    '!=': operator.ne
}


def binary_parse_action(tokens: ParseResults) -> Expression:
    # tokens[0] 为形如：[operand1, op, operand2, op, operand3, ...]
    t = tokens[0]
    expr = t[0]
    for i in range(1, len(t), 2):
        op = t[i]
        right = t[i + 1]
        expr = BinaryExpression(expr, right, binary_ops[op])
    return expr


expr = Forward()
#------------------------------------------------------------------------------
# 构造基元表达式：包括数值、标识符、括号内表达式
atom = (
    FLOAT | INT | OCT | HEX | SYMBOL | QUERY |
    (LPAREN + expr + RPAREN)  # 注意：后面我们将使用递归定义 expr
)


# 为支持函数调用和属性访问，构造后缀表达式：
# 例如： func(x,y).attr
def parse_function_call(expr_obj):
    # 参数列表可能为空，或者用逗号分隔的表达式列表
    arg_list = Optional(delimitedList(expr), default=[])
    return LPAREN + Group(arg_list) + RPAREN


postfix = Forward()
# 后缀可以是函数调用，也可以是属性访问
postfix_operation = ((parse_function_call(atom)
                      ).setParseAction(lambda t: ('CALL', t[0].asList())) |
                     (DOT + SYMBOL).setParseAction(lambda t: ('ATTR', t[0])))


# 定义 factor：先解析 atom，然后再依次处理后缀操作
def attach_postfix(tokens: ParseResults) -> Expression:
    # tokens[0] 为初始的 atom 对象
    expr_obj = tokens[0]
    # 遍历后缀操作序列
    for op, arg in tokens[1:]:
        if op == 'CALL':
            # 对于函数调用，arg 是参数列表，调用 __call__ 运算符（由 Expression.__call__ 实现）
            expr_obj = expr_obj(*arg)
        elif op == 'ATTR':
            # 对于属性访问，用 ObjectMethod 构造
            expr_obj = ObjectMethod(expr_obj, '__getattr__', arg)
    return expr_obj


# 将 atom 与后缀操作连接
postfix << (atom + Optional(
    (postfix_operation[...]))).setParseAction(attach_postfix)

#------------------------------------------------------------------------------
# 现在构造整个表达式解析器，利用 infixNotation 建立运算符优先级
expr <<= infixNotation(
    postfix,
    [
        (oneOf('! ~ + -'), 1, opAssoc.RIGHT, unary_parse_action),
        # 指数运算，右结合
        (Literal("**"), 2, opAssoc.RIGHT, binary_parse_action),
        (oneOf('* / // % @'), 2, opAssoc.LEFT, binary_parse_action),
        (oneOf('+ -'), 2, opAssoc.LEFT, binary_parse_action),
        (oneOf('<< >>'), 2, opAssoc.LEFT, binary_parse_action),
        (oneOf('&'), 2, opAssoc.LEFT, binary_parse_action),
        (oneOf('^'), 2, opAssoc.LEFT, binary_parse_action),
        (oneOf('|'), 2, opAssoc.LEFT, binary_parse_action),
        (oneOf('< <= > >= == !='), 2, opAssoc.LEFT, binary_parse_action),
    ])

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
        self.nested = {}
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
        return (key in self.consts or key in self.variables
                or key in self.functions or key in self.refs)

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
        if key in self.functions:
            raise KeyError(f"Key {key:r} is function")
        elif isinstance(value, Ref):
            self.create_ref(key, value.name)
        elif key in self.refs:
            self[self.refs[key]] = value
        else:
            self.variables[key] = value

    def __delitem__(self, key):
        if key in self.consts:
            raise KeyError(f"Key {key:r} is const")
        if key in self.functions:
            raise KeyError(f"Key {key:r} is function")
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
        elif self.method == '__getattr__':
            print(f"getattr {obj} {args}")
            return getattr(
                obj, *[a.name if isinstance(a, Symbol) else a for a in args])
        else:
            return getattr(obj, self.method)(*[
                a.value(env) if isinstance(a, Expression) else a for a in args
            ])

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
            value = env[self.name]
            if isinstance(value, Expression):
                return value.eval(env)
            else:
                return value
        else:
            return self

    def derivative(self, x):
        if x == self.name:
            return 1
        else:
            return 0

    def __repr__(self) -> str:
        return self.name


class Query(Symbol):

    def derivative(self, x):
        return 0

    def eval(self, env):
        return super().eval(env)


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


def calc(exp: str | Expression, env: Env = None, **kwargs) -> Expression:
    """
    Calculate the expression.

    Parameters
    ----------
    exp : str | Expression
        The expression to be calculated.
    env : Env, optional
        The environment to be used for the calculation. Default is _default_env.
    **kwargs : dict
        Additional arguments to be passed to the expression.

    Returns
    -------
    Expression
        The calculated expression.
    """
    if env is None:
        env = Env()
    for k, v in kwargs.items():
        env[k] = v
    if isinstance(exp, str):
        exp = expr.parseString(exp, parseAll=True)[0]
    return exp.eval(env)
