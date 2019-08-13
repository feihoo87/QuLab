import copy

class Variable(object):
    '''descriptor of variable, which is a tuple (value, unit).'''

    def __init__(self,value=None,unit=''):
        self.default_value=value
        self.default_unit=unit

    def __repr__(self):
        return 'Variable[default=(%s, %s)]' % (
                    self.default_value, self.default_unit)

    def __get__(self,instance,owner=None):
        if instance is None:
            return self
        else:
            return instance.__dict__[self]

    def __set__(self,instance,variable):
        if isinstance(variable,(tuple,list)):
            value,unit=variable
        elif isinstance(variable,dict):
            value=variable.get('value',None)
            unit=variable.get('unit','')
        elif isinstance(variable,(int,float,str)):
            value=variable
            unit=self.default_unit
        variable=(value,unit)
        instance.__dict__[self]=variable



class Quantity(object):

    def __init__(self,name,value=None,unit='',ch=None,
        get_cmd='',set_cmd='',type=None,):
        self.name = name
        self.set_cmd = set_cmd
        self.get_cmd = get_cmd
        self.type = type
        self.isglobal=True if ch is None else False
        ch = 'global' if ch is None else ch
        self.default = dict(value = value,
                            unit = unit,
                            ch = ch)

    def __repr__(self):
        return '''Quantity('%s')''' % (self.name)

    def _process_query(self, value):
        '''process the value query from Instrument before final return'''
        return value

    def get(self, driver, Driver=None, **kw):
        '''refer '__get__' of the descriptor in python'''
        if self.get_cmd is not '':
            cmd = self._formatGetCmd(**kw)
            value = driver.query(cmd)
            value = self._process_query(value)
        else:
            value=None
        return value

    def set(self, driver, value, **kw):
        '''refer '__set__' of the descriptor in python'''
        if  self.set_cmd is not '':
            cmd = self._formatSetCmd(value, **kw)
            driver.write(cmd)
        else:
            pass

    def _formatGetCmd(self, **kw):
        '''format the get_cmd'''
        _kw = copy.deepcopy(self.default)
        _kw.update(**kw)
        return self.get_cmd % dict(**_kw)

    def _pre_formatSetCmd(self,**kw):
        '''process the dict before formatSetCmd'''
        return kw

    def _formatSetCmd(self, value, **kw):
        '''format the set_cmd'''
        _kw = copy.deepcopy(self.default)
        _kw.update(value=value,**kw)
        _kw=self._pre_formatSetCmd(**_kw)
        return self.set_cmd % dict(**_kw)


class QReal(Quantity):
    def __init__(self,name,value=None,unit=None,ch=None,
                    get_cmd='',set_cmd='',):
        super().__init__(name,value,unit,ch,
            get_cmd=get_cmd,set_cmd=set_cmd,type='Real',)

    def _process_query(self, value):
        '''process the value query from Instrument before final return'''
        return value[0]

    def get(self, driver, Driver=None, **kw):
        '''refer '__get__' of the descriptor in python'''
        if self.get_cmd is not '':
            cmd = self._formatGetCmd(**kw)
            value = driver.query(cmd,mode='ascii')
            value = self._process_query(value)
        else:
            value=None
        return value


class QInteger(QReal):
    def __init__(self,name,value=None,unit=None,ch=None,
                    get_cmd='',set_cmd='',):
        super().__init__(name,value,unit,ch,
            get_cmd=get_cmd,set_cmd=set_cmd,)
        self.type='Integer'

    def _process_query(self, value):
        '''process the value query from Instrument before final return'''
        return int(value[0])

    def _pre_formatSetCmd(self,**kw):
        kw['value']=int(kw['value'])
        return kw


class QBool(QReal):
    def __init__(self,name,value=None,unit=None,ch=None,
                    get_cmd='',set_cmd='',):
        super().__init__(name,value,unit,ch,
            get_cmd=get_cmd,set_cmd=set_cmd,)
        self.type='Bool'

    def _process_query(self, value):
        '''process the value query from Instrument before final return'''
        return bool(value[0])

    def _pre_formatSetCmd(self,**kw):
        kw['value']=Bool(kw['value'])
        return kw


class QString(Quantity):
    def __init__(self,name,value=None,unit=None,ch=None,
                    get_cmd='',set_cmd='',):
        super().__init__(name,value,unit,ch,
            get_cmd=get_cmd,set_cmd=set_cmd,type='String',)

    def _process_query(self, value):
        '''process the value query from Instrument before final return'''
        return value.strip("\n\"' ")


class QOption(Quantity):
    def __init__(self,name,value=None,unit=None,ch=None,options=[],
                    get_cmd='',set_cmd='',):
        super().__init__(name,value,unit,ch,
            get_cmd=get_cmd,set_cmd=set_cmd,type='Option',)
        self.options=dict(options)
        _opts={}
        for k, v in self.options.items():
            _opts[v]=k
        self._opts=_opts

    def _process_query(self, value):
        '''process the value query from Instrument before final return'''
        _value = value.strip("\n\"' ")
        value = self._opts[_value]
        return value

    def _pre_formatSetCmd(self,**kw):
        assert kw['value'] in self.options.keys()
        kw['option']=self.options.get(kw['value'])
        return kw


class QVector(Quantity):
    def __init__(self,name,value=None,unit=None,ch=None,
                    get_cmd='',set_cmd='',):
        super().__init__(name,value,unit,ch,
            get_cmd=get_cmd,set_cmd=set_cmd,type='Vector',)

    def _process_query(self, value):
        '''process the value query from Instrument before final return'''
        value = np.asarray(value)
        return value


class QList(Quantity):
    def __init__(self,name,value=None,unit=None,ch=None,
                    get_cmd='',set_cmd='',):
        super().__init__(name,value,unit,ch,
            get_cmd=get_cmd,set_cmd=set_cmd,type='List',)



def newcfg(quantlist=[],CHs=[]):
    '''generate a new config'''
    config={}
    for q in copy.deepcopy(quantlist):
        _cfg={}
        _default=dict(value=q.default['value'], unit=q.default['unit'])
        if q.isglobal:
            _cfg.update({'global':copy.deepcopy(_default)})
        else:
            for i in CHs:
                _cfg.update({i:copy.deepcopy(_default)})
        config.update({q.name:_cfg})
    return config
