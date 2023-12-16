import ast

import numpy as np

from .base import scan_iters
from .expression import Env, Expression, Symbol, _empty


def is_valid_identifier(s: str) -> bool:
    try:
        ast.parse(f"f({s}=0)")
        return True
    except SyntaxError:
        return False


class Atom():
    __slots__ = ('value', )

    def __init__(self, value):
        self.value = value


class MappedSymbol(Symbol):
    pass


class OptimizeSpace():

    def __init__(self, optimizer, space):
        self.optimizer = optimizer
        self.space = space
        self.name = None


class Optimizer():

    def __init__(self, cls, *args, **kwds):
        self.cls = cls
        self.args = args
        self.kwds = kwds
        self.dimensions = {}
        self.function = None

    def Categorical(self, *args, **kwds):
        from skopt.space import Categorical
        return OptimizeSpace(self, Categorical(*args, **kwds))

    def Integer(self, *args, **kwds):
        from skopt.space import Integer
        return OptimizeSpace(self, Integer(*args, **kwds))

    def Real(self, *args, **kwds):
        from skopt.space import Real
        return OptimizeSpace(self, Real(*args, **kwds))

    @property
    def target(self):
        return None

    @target.setter
    def target(self, fun):
        if isinstance(fun, Symbol):
            self.function = fun.name
        elif isinstance(fun, Expression):
            self.function = fun
        else:
            raise ValueError("Invalid function")

    def create_optimizer(self):
        dimensions = list(self.dimensions.values())
        return tuple(self.dimensions.keys()), self.cls(dimensions, *self.args,
                                                       **self.kwds)


class Scan():

    def __new__(cls, *args, mixin=None, **kwds):
        if mixin is None:
            return super().__new__(cls)
        for k in dir(mixin):
            if not hasattr(cls, k):
                try:
                    setattr(cls, k, getattr(mixin, k))
                except:
                    pass
        return super().__new__(cls)

    def __init__(self, name, *args, env=None, mixin=None, **kwds):
        super().__init__(*args, **kwds)
        self._name = name.replace(' ', '_')
        self.env = Env() if env is None else env
        self.functions = {}
        self.consts = {}
        self.loops = {}
        self.mapping = {}
        self.optimizers = {}
        self._mapping_i = 0
        self.filter = None
        self.scan_info = {'loops': {}}
        self._tmp = {}

    @property
    def name(self):
        return f"Scan.{self._name}"

    def get(self, key, default=_empty):
        if key in self.consts:
            return self.consts[key]
        if key in self.functions:
            return self.functions[key]
        if default is _empty:
            raise KeyError(f"Key {key} not found")
        return default

    def set(self, key, value):
        print(f"Set {key} to {value}")

    def _mapping(self, key, value):
        tmpkey = f"__tmp_{self._mapping_i}__"
        self._mapping_i += 1
        self[tmpkey] = value
        self.mapping[key] = tmpkey

    def __setitem__(self, key, value):
        if is_valid_identifier(key):
            if isinstance(value, Atom):
                self.consts[key] = value.value
                return
            elif isinstance(value, (str, int, float, complex, tuple)):
                self.consts[key] = value
                return

        if isinstance(value, Expression):
            env = Env()
            env.consts = self.consts
            value = value.value(env)
            if not isinstance(value, Expression):
                self.__setitem__(key, value)
                return

        self._tmp[key] = value

    def __setitem(self, key, value):
        if not is_valid_identifier(key):
            self._mapping(key, value)
            return
        if isinstance(value, Expression) or callable(value):
            self.functions[key] = value
        elif isinstance(value, OptimizeSpace):
            self.optimizers[key] = value.optimizer
            value.name = key
            value.optimizer.dimensions[key] = value.space
            self.loops[key] = value.optimizer
        elif isinstance(value, (np.ndarray, list, range)):
            self.loops[key] = value
        elif isinstance(value, Atom):
            self.consts[key] = value.value
        else:
            self.consts[key] = value

    def __getitem__(self, key):
        if key in self.consts:
            return self.consts[key]
        if is_valid_identifier(key):
            return Symbol(key)
        else:
            if key in self.mapping:
                return Symbol(self.mapping[key])
            return MappedSymbol(key)

    def assemble(self):
        for key, value in self._tmp.items():
            self.__setitem(key, value)

        variables = {}
        loops = {}

        for k, v in self.functions.items():
            if isinstance(v, MappedSymbol):
                variables[k] = eval(
                    f"lambda {self.mapping[k]}: {self.mapping[k]}")
            elif isinstance(v, Expression):
                args = v.symbols()
                for x in args:
                    if x in self.mapping:
                        args.remove(x)
                        v = v.value({x: Symbol(self.mapping[x])})
                        x = self.mapping[x]
                    if x in self.consts:
                        args.remove(x)
                        v = v.value({x: self.consts[x]})
                if args:
                    variables[k] = eval(
                        f"lambda {','.join(args)}: expr.value({{{','.join([f'{x!r}:{x}' for x in args])}}})",
                        {'expr': v})
                else:
                    self.consts[k] = v
            else:
                variables[k] = v

        for key, value in self.loops.items():
            if isinstance(value, Optimizer):
                #variables[key] = value.create_optimizer()
                pass
            else:
                loops[key] = value

        self.scan_info = {
            'loops': loops,
            'functions': variables,
            'constants': self.consts
        }

        if self.filter is not None:
            self.scan_info['filter'] = self.filter

    def main(self):
        self.assemble()
        for step in self.scan():
            for k, v in self.mapping.items():
                self.set(k, step.kwds[v])
            self.process(step)

    def process(self, step):
        print(step.kwds)

    def scan(self):
        for step in scan_iters(**self.scan_info):
            for k, v in self.mapping.items():
                step.kwds[k] = step.kwds[v]
            yield step

    def run(self, dry_run=False):
        pass

    def plot(self,
             result=None,
             fig=None,
             axis=None,
             data='population',
             T=False,
             **kwds):
        pass
