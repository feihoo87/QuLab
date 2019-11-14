import redis
import pickle
import time
import numpy as np
import functools

from .redisclient import redisString, redisList, redisSet, redisZSet
from . import save_backends as backends

class dataCollector(object):
    
    def __init__(self,name,dim=1,zshape=1,server=None,addr='redis://localhost:6379/0',expire_time=172800):
        '''数据收集器

        Parameter:
            name: 名字(字符串)，用来在Redis中创建一系列的键
            dim: 维度(整数)，即扫描参数的个数
            zshape: 一组参数对应的数据的形状(整数或者元素为整数的元组)
            server: 已连接的Redis对象，优先于addr使用(如果为None，则根据addr产生一个)
            addr: 一个Redis数据库的地址，在server参数为None时使用
            expire_time: 数据的过期时间，单位秒，默认两天
        '''
        self.name=name
        axis=[]
        for i in range(dim):
            _name=f'{name}_ax{i}'
            axis.append(redisZSet(_name,server,addr,expire_time))
        self.axis=axis
        self.dim=dim
        
        _name=f'{name}_zlist'
        self.z=redisList(_name,server,addr,expire_time)
        self.zshape=zshape if isinstance(zshape,tuple) else (zshape,)
    
    def delete(self):
        for ax in self.axis:
            ax.delete()
        self.z.delete()
        
    def add(self,*arg):
        for i,ax in enumerate(self.axis):
            _arg=np.asarray(arg[i]).flatten()
            ax.add(*_arg)
        _z=functools.reduce(np.append,[np.asarray(_a).flatten() for _a in arg[i+1:]])
        self.z.add(*_z)

    def _ztoarray(self,moveaxis=False):
        data_raw=np.asarray(self.z.data).flatten()
        size_raw=data_raw.size
        if self.size>size_raw:          
            zeros=[0]*(self.size-size_raw)
            data=np.append(data_raw,zeros)
        else:
            data=data_raw[:self.size]
        data_array=np.asarray(data).reshape(self.shape)
        if moveaxis:
            # 对 data array 进行移轴，使之更便于读取
            data_array=np.moveaxis(data_array,self.dim,0) if self.zshape!=(1,) else data_array
        return data_array
    
    def read(self,moveaxis=False):
        axis_data=(np.array(ax.data) for ax in self.axis)
        z_array=self._ztoarray(moveaxis)
        return (*axis_data,z_array)
            
    @property
    def shape(self):
        shape_axis=[zset.size for zset in self.axis]
        shape=(*shape_axis,*self.zshape) if self.zshape!=(1,) else tuple(shape_axis)
        return shape
    
    @property
    def size(self):
        # s=1
        # for v in self.shape:
        #     s=s*v
        ## 等价于
        s=functools.reduce(lambda a,b:a*b, self.shape)
        return s
    
    @property
    def data(self):
        return self.read(moveaxis=False)    

class redisRecord(object):
    
    def __init__(self,name,dim=1,zshape=1,server=None,
                addr='redis://localhost:6379/0',save_backend='dat',autosave=True,expire_time=172800):
        self.name=name
        self.collector=dataCollector(name,dim,zshape,server,addr,expire_time)
        
        _name=f'{name}_config'
        self.cfg=redisString(_name,server,addr,expire_time)
        _name=f'{name}_setting'
        self.st=redisString(_name,server,addr,expire_time)
        _name=f'{name}_tags'
        self.tg=redisSet(_name,server,addr,expire_time)

        _name=f'{name}_isactive'
        self.isactive=redisString(_name,server,addr,expire_time)

        self.save_backend=save_backend
        self.autosave=autosave
    
    def delete(self):
        self.collector.delete()
        self.cfg.delete()
        self.st.delete()
        self.tg.delete()
        self.isactive.delete()
        
    def set(self,config=None,setting=None,tags=None):
        self.cfg.delete()
        self.st.delete()
        self.tg.delete()
        if config is not None:
            self.cfg.set(config)
        if setting is not None:
            self.st.set(setting)
        if tags is not None:
            self.tg.add(*tags)
        
    def collect(self,*arg):
        self.collector.add(*arg)
    
    @property
    def data(self):
        return self.collector.data
    
    @property
    def tags(self):
        return self.tg.read()
    
    @property
    def config(self):
        return self.cfg.get()
    
    @property
    def setting(self):
        return self.st.get()

    def save(self,backend=None):
        '''将记录保存

        Parameter:
            backend: 由事先定义的后端名字与模式组成的字符串，
                使用用.连接多个bk，如果有mode参数则使用@分割，比如 'dat.fig@pdf'
        Return:
            ID列表
        '''
        if backend is None:
            backend = self.save_backend
        bk_list=backend.split('.')
        id_list=[]
        for bkm in bk_list:
            if bkm.count('@'):
                bk,mode=bkm.split('@')
                kw=dict(mode=mode)
            else:
                bk=bkm
                kw=dict()
            save_func=getattr(backends,bk)
            _id = save_func(self,**kw)
            id_list.append(_id)
        return id_list

    @staticmethod
    def load(file):
        with open(file,'rb') as f:
            record_b=f.read()
        record=pickle.loads(record_b)
        return record
    
    def __enter__(self):
        self.collector.delete()
        self.isactive.set(True)
        
    def __exit__(self,t,val,tb):
        self.isactive.set(False)
        if self.autosave and self.collector.z.size>0:
            self.save()      