import redis
import pickle
import time
from pathlib import Path
import numpy as np
import functools

from .redisclient import redisString, redisList, redisSet, redisZSet

from qulab import config

storage_cfg = config.get('storage', {})

class dataCollector(object):
    
    def __init__(self,name,dim=1,zshape=1,server=None,addr='redis://localhost:6379/0'):
        self.name=name
        axis=[]
        for i in range(dim):
            _name=f'{name}_ax{i}'
            axis.append(redisZSet(_name,server,addr))
        self.axis=axis
        self.dim=dim
        
        _name=f'{name}_zlist'
        self.z=redisList(_name,server,addr)
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

    def _ztoarray(self):
        data_raw=np.asarray(self.z.data).flatten()
        size_raw=data_raw.size
        if self.size>size_raw:          
            zeros=[0]*(self.size-size_raw)
            data=np.append(data_raw,zeros)
        else:
            data=data_raw[:self.size]
        data_array=np.asarray(data).reshape(self.shape)
        return data_array
    
    def read(self):
        axis_data=(np.array(ax.data) for ax in self.axis)
        z_array=self._ztoarray()
        return (*axis_data,z_array)
            
    @property
    def shape(self):
        shape_axis=[zset.size for zset in self.axis]
        shape=(*shape_axis,*self.zshape) if self.zshape!=(1,) else tuple(shape_axis)
        return shape
    
    @property
    def size(self):
        s=1
        for v in self.shape:
            s=s*v
        return s
    
    @property
    def data(self):
        return self.read()    

class redisRecord(object):
    
    def __init__(self,name,dim=1,zshape=1,server=None,
                addr='redis://localhost:6379/0',autosave=True,):
        self.name=name
        self.collector=dataCollector(name,dim,zshape,server,addr)
        
        _name=f'{name}_config'
        self.cfg=redisString(_name,server,addr)
        _name=f'{name}_setting'
        self.st=redisString(_name,server,addr)
        _name=f'{name}_tags'
        self.tg=redisSet(_name,server,addr)

        _name=f'{name}_isactive'
        self.isactive=redisString(_name,server,addr)
        self.isactive.set(False)

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

    def save(self,base_path=None,mode='both'):
        if base_path is None:
            # base_path = Path(str('D:'))   
            base_path = Path(storage_cfg.get('data_path', Path.cwd()))
        else:
            base_path = Path(base_path)

        path = base_path / time.strftime('%Y') / time.strftime('%m%d')
        path.mkdir(parents=True, exist_ok=True)

        res=[]

        if mode in ['both','data']:
            args=self.data
            if len(args)==3:
                x,y,z=args
                kw=dict(x=x,y=y,z=z)
            elif len(args)==2:
                x,z=args
                kw=dict(x=x,z=z)
            else:
                raise
            fname = f"{self.name}_{time.strftime('%Y%m%d%H%M%S')}.npz"
            np.savez_compressed(path / fname, **kw)
            print(path / fname)
            res.append(path / fname)

        if mode in ['both','record']:
            record = {}
            record.update(
                config=self.config,
                setting=self.setting,
                tags=self.tags,
                data=self.data
            )
            record_b=pickle.dumps(record)
            fname = f"{self.name}_record{time.strftime('%Y%m%d%H%M%S')}.txt"
            with open(path / fname,'wb') as f:
                f.write(record_b)
            print(path / fname)
            res.append(path / fname)
        return tuple(res)

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
        if self.autosave and self.collector.z.size>0:
            self.save(mode='both')
        self.isactive.set(False)