class Space():
    pass


class OptimizeSpace(Space):
    pass


class Expression():
    def __init__(self, name: str, scan):
        self.name = name
        self.scan = scan


class Optimizer():

    def __init__(self, scan, minimize=True):
        self.scan = scan
        self.minimize = minimize
        self.codes = []

    def search(self, name: str, space: OptimizeSpace, setter=None):
        self.codes.append(('search', name, space, setter))
        return self


class Scan():

    def __init__(self):
        self.codes = []

    def set(self, name: str, value, setter=None):
        self.codes.append(('set', name, value, setter))
        return self

    def get(self, name: str, getter=None):
        self.codes.append(('get', name, getter))
        return Expression(name, self)

    def search(self, name: str, space: Space, level:int, setter=None):
        self.codes.append(('search', name, space, level, setter))
        return self

    def minimize(self, name: str, getter=None) -> Optimizer:
        opt = Optimizer(self, minimize=True)
        self.codes.append(('minimize', name, opt, getter))
        return opt

    def maximize(self, name: str, getter=None) -> Optimizer:
        opt = Optimizer(self, minimize=False)
        self.codes.append(('maximize', name, opt, getter))
        return opt
