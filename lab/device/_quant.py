# -*- coding: utf-8 -*-
import numpy as np

from ..util import get_unit_prefix


class Quantity(object):
    def __init__(self, name, value=None, type=None, unit=None, ch=None, get_cmd='', set_cmd=''):
        self.name = name
        self.value = value
        self.type = type
        self.unit = unit
        self.ch = ch
        self.driver = None
        self.set_cmd = set_cmd
        self.get_cmd = get_cmd

    def __str__(self):
        return '%s' % self.value

    def setDriver(self, driver):
        self.driver = driver

    def getValue(self, ch=None, **kw):
        if ch is None:
            ch=self.ch
        return self.value

    def setValue(self, value, unit=None, ch=None, **kw):
        self.value = value
        if ch is None:
            ch=self.ch
        if unit is None:
            unit=self.unit
        if self.driver is not None and self.set_cmd is not '':
            cmd = self._formatSetCmd(value, unit, ch, **kw)
            self.driver.write(cmd)

    def _formatGetCmd(self, ch, **kw):
        return self.get_cmd % dict(ch=ch,**kw)

    def _formatSetCmd(self, value, unit, ch, **kw):
        return self.set_cmd % dict(value=value, unit=unit, ch=ch, **kw)


class QReal(Quantity):
    def __init__(self, name, value=None, unit=None, ch=None, get_cmd='', set_cmd=''):
        super(QReal, self).__init__(name, value, 'Real', unit, ch, get_cmd=get_cmd, set_cmd=set_cmd)

    def __str__(self):
        p, r = get_unit_prefix(self.value)
        value = self.value/r
        unit = p+self.unit
        return '%g %s' % (value, unit)

    def getValue(self, ch=None, **kw):
        if ch is None:
            ch=self.ch
        if self.driver is not None and self.get_cmd is not '':
            cmd = self._formatGetCmd(ch, **kw)
            res = self.driver.query_ascii_values(cmd)
            self.value = res[0]
        return self.value


class QInteger(QReal):
    def __init__(self, name, value=None, unit=None, ch=None, get_cmd='', set_cmd=''):
        Quantity.__init__(self, name, value, 'Integer', unit, ch, get_cmd=get_cmd, set_cmd=set_cmd)

    def getValue(self, ch=None, **kw):
        if ch is None:
            ch=self.ch
        super(QInteger, self).getValue(ch, **kw)
        return int(self.value)


class QString(Quantity):
    def __init__(self, name, value=None, ch=None, get_cmd='', set_cmd=''):
        super(QString, self).__init__(name, value, 'String', ch=ch, get_cmd=get_cmd, set_cmd=set_cmd)

    def getValue(self, ch=None, **kw):
        if ch is None:
            ch=self.ch
        if self.driver is not None and self.get_cmd is not '':
            cmd = self._formatGetCmd(ch, **kw)
            res = self.driver.query(cmd)
            self.value = res.strip("\n\"' ")
        return self.value


class QOption(QString):
    def __init__(self, name, value=None, options=[], ch=None, get_cmd='', set_cmd=''):
        Quantity.__init__(self, name, value, 'Option', ch=ch, get_cmd=get_cmd, set_cmd=set_cmd)
        self.options = options
        self._opts = {}
        for k,v in self.options:
            self._opts[k] = v
            self._opts[v] = k

    def setValue(self, value, ch=None, **kw):
        self.value = value
        if ch is None:
            ch=self.ch
        if self.driver is not None and self.set_cmd is not '':
            options = dict(self.options)
            if value not in options.keys():
                #logger.error('%s not in %s options' % (value, self.name))
                return
            cmd = self.set_cmd % dict(option = options[value], ch=ch, **kw)
            self.driver.write(cmd)

    def getIndex(self,ch=None, **kw):
        if ch is None:
            ch=self.ch
        value = self.getValue(ch,**kw)
        if value is None:
            return None

        for i, pair in enumerate(self.options):
            if pair[0] == value:
                return i
        return None

    def getCmdOption(self,ch=None, **kw):
        if ch is None:
            ch=self.ch
        value = self.getValue(ch,**kw)
        if value is None:
            return None
        return dict(self.options)[value]


class QBool(QInteger):
    def __init__(self, name, value=None, ch=None, get_cmd='', set_cmd=''):
        Quantity.__init__(self, name, value, 'Bool', ch=ch, get_cmd=get_cmd, set_cmd=set_cmd)

    def getValue(self,ch=None, **kw):
        if ch is None:
            ch=self.ch
        return bool(super(QBool, self).getValue(ch, **kw))


class QVector(Quantity):
    def __init__(self, name, value=None, unit=None, ch=None, get_cmd='', set_cmd=''):
        super(QVector, self).__init__(name, value, 'Vector', unit, ch, get_cmd=get_cmd, set_cmd=set_cmd)

    def getValue(self,ch=None, **kw):
        if ch is None:
            ch=self.ch
        if self.driver is not None and self.get_cmd is not '':
            cmd = self._formatGetCmd(ch,**kw)
            if kw.get('binary'):
                res = self.driver.query_binary_values(cmd)
            else:
                res = self.driver.query_ascii_values(cmd)
            self.value = np.asarray(res)
        return self.value


class QList(Quantity):
    def __init__(self, name, value=None, unit=None, ch=None, get_cmd='', set_cmd=''):
        super(QList, self).__init__(name, value, 'List', unit, ch, get_cmd=get_cmd, set_cmd=set_cmd)
