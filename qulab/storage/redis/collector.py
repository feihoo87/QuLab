import redis
import pickle
import time
import datetime
from pathlib import Path
import numpy as np
import functools

from .redisclient import redisString, redisList, redisSet, redisZSet

from qulab import config

storage_cfg = config.get('storage', {})

class dataCollector(object):
    
    def __init__(self,name,dim=1,zshape=1,server=None,addr='redis://localhost:6379/0',expire_time=604800):
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
        s=1
        for v in self.shape:
            s=s*v
        return s
    
    @property
    def data(self):
        return self.read(moveaxis=False)    

class redisRecord(object):
    
    def __init__(self,name,dim=1,zshape=1,server=None,
                addr='redis://localhost:6379/0',save_backend='both',autosave=True,expire_time=604800):
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
        self.isactive.set(False)

        self.save_backend=save_backend
        self.autosave=autosave

        self.created_time=datetime.datetime.now()
        self.finished_time=datetime.datetime.now()
    
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

    def save(self,base_path=None,backend=None):
        if base_path is None:
            # base_path = Path(str('D:'))   
            base_path = Path(storage_cfg.get('data_path', Path.cwd()))
        else:
            base_path = Path(base_path)

        if backend is None:
            backend = self.save_backend

        record = dict(
                config=self.config,
                setting=self.setting,
                tags=self.tags,
                data=self.data
            )

        path = base_path / time.strftime('%Y') / time.strftime('%m%d')
        path.mkdir(parents=True, exist_ok=True)
        fname_raw=f"{self.name}_{time.strftime('%Y%m%d%H%M%S')}"

        res=[]

        if backend in ['both','npz']:
            fname = f"{fname_raw}.npz"
            args=record['data']
            if len(args)==3:
                x,y,z=args
                kw=dict(x=x,y=y,z=z)
                np.savez_compressed(path / fname, **kw)
            elif len(args)==2:
                x,z=args
                kw=dict(x=x,z=z)
                np.savez_compressed(path / fname, **kw)
            else:
                np.savez_compressed(path / fname, *args)
            print(path / fname)
            res.append(path / fname)

        if backend in ['both','dat']:   
            record_b=pickle.dumps(record)
            fname = f"{fname_raw}.dat"
            with open(path / fname,'wb') as f:
                f.write(record_b)
            print(path / fname)
            res.append(path / fname)

        if backend in ['mongo']:
            pass
        return tuple(res)

    @staticmethod
    def load(file):
        with open(file,'rb') as f:
            record_b=f.read()
        record=pickle.loads(record_b)
        return record
    
    def __enter__(self):
        self.created_time=datetime.datetime.now()     
        self.collector.delete()
        self.isactive.set(True)
        
    def __exit__(self,t,val,tb):
        self.finished_time=datetime.datetime.now()
        if self.autosave and self.collector.z.size>0:
            self.save()
        self.isactive.set(False)