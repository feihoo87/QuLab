# -*- coding: utf-8 -*-
from ..util import get_unit_prefix

class Quantity(object):
    def __init__(self, name, value=None, type=None, unit=None, get_cmd='', set_cmd=''):
        self.name = name
        self.value = value
        self.type = type
        self.unit = unit
        self.driver = None
        self.set_cmd = set_cmd
        self.get_cmd = get_cmd

    def __str__(self):
        return '%s' % self.value

    def setDriver(self, driver):
        self.driver = driver

    def getValue(self, **kw):
        return self.value

    def setValue(self, value, **kw):
        self.value = value
        if self.driver is not None and self.set_cmd is not '':
            cmd = self._formatSetCmd(value, **kw)
            self.driver.write(cmd)

    def _formatGetCmd(self, **kw):
        return self.get_cmd % dict(**kw)

    def _formatSetCmd(self, value, **kw):
        return self.set_cmd % dict(value=value, **kw)

class QReal(Quantity):
    def __init__(self, name, value=None, unit=None, get_cmd='', set_cmd=''):
        super(QReal, self).__init__(name, value, 'Real', unit, get_cmd=get_cmd, set_cmd=set_cmd)

    def __str__(self):
        p, r = get_unit_prefix(self.value)
        value = self.value/r
        unit = p+self.unit
        return '%g %s' % (value, unit)

    def getValue(self, **kw):
        if self.driver is not None and self.get_cmd is not '':
            cmd = self._formatGetCmd(**kw)
            res = self.driver.query_ascii_values(cmd)
            self.value = res[0]
        return self.value

class QInteger(QReal):
    def __init__(self, name, value=None, unit=None, get_cmd='', set_cmd=''):
        Quantity.__init__(self, name, value, 'Integer', unit, get_cmd=get_cmd, set_cmd=set_cmd)

    def getValue(self, **kw):
        super(QInteger, self).getValue(**kw)
        return int(self.value)

class QString(Quantity):
    def __init__(self, name, value=None, get_cmd='', set_cmd=''):
        super(QString, self).__init__(name, value, 'String', get_cmd=get_cmd, set_cmd=set_cmd)

    def getValue(self, **kw):
        if self.driver is not None and self.get_cmd is not '':
            cmd = self._formatGetCmd(**kw)
            res = self.driver.query(cmd)
            self.value = res.strip()
        return self.value

class QOption(QString):
    def __init__(self, name, value=None, options=[], get_cmd='', set_cmd=''):
        Quantity.__init__(self, name, value, 'Option', get_cmd=get_cmd, set_cmd=set_cmd)
        self.options = options
        self._opts = {}
        for k,v in self.options:
            self._opts[k] = v
            self._opts[v] = k

    def setValue(self, value, **kw):
        self.value = value
        if self.driver is not None and self.set_cmd is not '':
            options = dict(self.options)
            if value not in options.keys():
                #logger.error('%s not in %s options' % (value, self.name))
                return
            cmd = self.set_cmd % dict(option = options[value], **kw)
            self.driver.write(cmd)

    def getIndex(self, **kw):
        value = self.getValue(**kw)
        if value is None:
            return None

        for i, pair in enumerate(self.options):
            if pair[0] == value:
                return i
        return None

    def getCmdOption(self, **kw):
        value = self.getValue(**kw)
        if value is None:
            return None
        return dict(self.options)[value]

class QBool(Quantity):
    def __init__(self, name, value=None, get_cmd='', set_cmd=''):
        super(QBool, self).__init__(name, value, 'Bool', get_cmd=get_cmd, set_cmd=set_cmd)

    def getValue(self, **kw):
        return bool(super(QBool, self).getValue(**kw))

class QVector(Quantity):
    def __init__(self, name, value=None, unit=None, get_cmd='', set_cmd=''):
        super(QVector, self).__init__(name, value, 'Vector', unit, get_cmd=get_cmd, set_cmd=set_cmd)

    def getValue(self, **kw):
        if self.driver is not None and self.get_cmd is not '':
            cmd = self._formatGetCmd(**kw)
            if kw.get('binary'):
                res = self.driver.query_binary_values(cmd)
            else:
                res = self.driver.query_ascii_values(cmd)
            self.value = res
        return self.value
