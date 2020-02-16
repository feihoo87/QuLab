import redis
import pickle
import time
from pathlib import Path
import numpy as np
import functools

class redisClient(object):
    
    def __init__(self,name,server=None,addr='redis://localhost:6379/0',expire_time=172800):
        self._r=redis.Redis.from_url(addr) if server is None else server
        self.name=name
        self.expire_time=expire_time # 默认数据两天过期，单位秒
        
    def delete(self):
        self._r.delete(self.name)
                  
class redisString(redisClient):
    '''Redis String client'''

    def set(self,value):
        if value is not None:
            value_b=pickle.dumps(value) 
            self._r.set(self.name,value_b,ex=self.expire_time)
    
    def get(self):
        value_b=self._r.get(self.name)
        value=pickle.loads(value_b) if value_b is not None else None
        return value

    @property
    def data(self):
        return self.get()

class redisList(redisClient):
    '''Redis List client'''
    def add(self,*arg):
        arg_b=[pickle.dumps(i) for i in arg]
        self._r.rpush(self.name,*arg_b)
        self._r.expire(self.name,self.expire_time)
    
    def read(self,start=0,end=-1):
        data_b=self._r.lrange(self.name,start,end)
        data=[pickle.loads(i) for i in data_b]
        return data
    
    @property
    def size(self):
        return self._r.llen(self.name)
    
    @property
    def data(self):
        return self.read()

class redisSet(redisClient):
    '''Redis Set client'''
    def add(self,*arg):
        arg_b={pickle.dumps(i) for i in arg}
        self._r.sadd(self.name,*arg_b)
        self._r.expire(self.name,self.expire_time)
    
    def read(self):
        data_b=self._r.smembers(self.name)
        data={pickle.loads(i) for i in data_b}
        return data
    
    @property
    def size(self):
        return self._r.scard(self.name)
    
    @property
    def data(self):
        return self.read()
    
class redisZSet(redisClient):
    '''有序集合'''
    
    def __init__(self,name,server=None,addr='redis://localhost:6379/0',expire_time=172800):
        super().__init__(name,server,addr,expire_time)
        self.__score=0
        
    def delete(self):
        super().delete()
        self.__score=0
    
    def add(self,*elements):
        mapping={}
        for ele in elements:
            ele_b=pickle.dumps(ele)
            self.__score+=1
            mapping.update({ele_b:self.__score})
        self._r.zadd(self.name,mapping,nx=True) #只添加新元素
        self._r.expire(self.name,self.expire_time)
    
    def read(self,start=0,end=-1):
        data_b=self._r.zrange(self.name,start,end,withscores=False)
        data=[pickle.loads(i) for i in data_b]
        return data
    
    @property
    def size(self):
        return self._r.zcard(self.name)
    
    @property
    def data(self):
        return self.read()
