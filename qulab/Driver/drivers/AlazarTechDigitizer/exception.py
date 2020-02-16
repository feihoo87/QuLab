class AlazarTechError(Exception):
    def __init__(self, code, msg):
        super(AlazarTechError, self).__init__(msg)
        self.code = code
        self.msg = msg

    def __repr__(self):
        return f"AlazarTechError({self.code}, '{self.msg}')"
