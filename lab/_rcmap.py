class RcMap:
    def __init__(self, rc={}, parent=None):
        self.rc = {}
        self.parent = parent
        self.rc.update(rc)

    def update(self, rc={}):
        self.rc.update(rc)

    def items(self):
        return [(name, self.__getitem__(name)) for name in self.keys()]

    def keys(self):
        keys = set(self.rc.keys())
        if self.parent is not None:
            keys = keys.union(self.parent.keys())
        return list(keys)

    def get(self, name, default=None):
        if name in self.keys():
            return self.get_resource(name)
        elif default is None:
            raise KeyError('key %r not found in RcMap.' % name)
        else:
            return default

    def get_resource(self, name):
        name = self.rc.get(name, name)
        if not isinstance(name, str):
            return name
        elif self.parent is not None:
            return self.parent.get_resource(name)
        else:
            from ._bootstrap import open_resource
            return open_resource(name)

    def __getitem__(self, name):
        return self.get(name)
