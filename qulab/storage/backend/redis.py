import dill
import numpy as np
import redis


def try_dumps(value):
    try:
        value_b = dill.dumps(value)
    except:
        value_b = dill.dumps(str(value))
    finally:
        return value_b


class redisClient(object):

    def __init__(self,
                 name,
                 server=None,
                 addr='redis://localhost:6379/0',
                 expire_time=172800):
        self._r = redis.Redis.from_url(addr) if server is None else server
        self.name = name
        self.expire_time = int(expire_time)  # 默认数据两天过期，单位秒

    def delete(self):
        self._r.delete(self.name)


class redisString(redisClient):
    '''Redis String client'''

    def set(self, value):
        if value is not None:
            value_b = try_dumps(value)
            self._r.set(self.name, value_b, ex=self.expire_time)

    def get(self):
        v_b = self._r.get(self.name)
        value = dill.loads(v_b) if v_b is not None else None
        return value

    @property
    def data(self):
        return self.get()


class redisList(redisClient):
    '''Redis List client'''

    def add(self, *arg):
        arg_b = [dill.dumps(i) for i in arg]
        self._r.rpush(self.name, *arg_b)
        self._r.expire(self.name, self.expire_time)

    def read(self, start=0, end=-1):
        data_b = self._r.lrange(self.name, start, end)
        data = [dill.loads(i) for i in data_b]
        return data

    @property
    def size(self):
        return self._r.llen(self.name)

    @property
    def data(self):
        return self.read()


class redisSet(redisClient):
    '''Redis Set client'''

    def add(self, *arg):
        arg_b = {dill.dumps(i) for i in arg}
        self._r.sadd(self.name, *arg_b)
        self._r.expire(self.name, self.expire_time)

    def read(self):
        data_b = self._r.smembers(self.name)
        data = {dill.loads(i) for i in data_b}
        return data

    @property
    def size(self):
        return self._r.scard(self.name)

    @property
    def data(self):
        return self.read()


class redisZSet(redisClient):
    '''有序集合'''

    def __init__(self,
                 name,
                 server=None,
                 addr='redis://localhost:6379/0',
                 expire_time=172800):
        super().__init__(name, server, addr, expire_time)
        self.__score = 0

    def delete(self):
        super().delete()
        self.__score = 0

    def add(self, *elements):
        mapping = {}
        for ele in elements:
            ele_b = dill.dumps(ele)
            self.__score += 1
            mapping.update({ele_b: self.__score})
        self._r.zadd(self.name, mapping, nx=True)  # 只添加新元素
        self._r.expire(self.name, self.expire_time)

    def read(self, start=0, end=-1):
        data_b = self._r.zrange(self.name, start, end, withscores=False)
        data = [dill.loads(i) for i in data_b]
        return data

    @property
    def size(self):
        return self._r.zcard(self.name)

    @property
    def data(self):
        return self.read()


class redisHash(redisClient):
    '''Redis Hash client'''

    def add(self, **kw):
        kw_b = {k: try_dumps(v) for k, v in kw.items()}
        self._r.hmset(self.name, kw_b)
        self._r.expire(self.name, self.expire_time)

    def read(self):
        data_b = self._r.hgetall(self.name)
        data = {k_b.decode(): dill.loads(v_b) for k_b, v_b in data_b.items()}
        return data

    def get(self, key):
        '''读取Hash中的一个key'''
        v_b = self._r.hget(self.name, key)
        value = dill.loads(v_b) if v_b is not None else None
        return value

    @property
    def size(self):
        return self._r.hlen(self.name)

    @property
    def data(self):
        return self.read()


class redisArray(redisClient):
    '''Redis np.array client'''

    def __init__(self,
                 name,
                 server=None,
                 addr='redis://localhost:6379/0',
                 expire_time=172800,
                 dtype='complex128'):
        super().__init__(name, server, addr, expire_time)
        _r_dtype = self._r.get(f'{name}.dtype')
        if _r_dtype is None:
            self._r.set(f'{name}.dtype', dtype, ex=self.expire_time)
            self.dtype = dtype
        else:
            self.dtype = _r_dtype

    def delete(self):
        self._r.delete(self.name)
        self._r.delete(f'{self.name}.dtype')

    def add(self, *args):
        for arg in args:
            buf = np.asarray(arg).astype(self.dtype).tobytes()
            # self._r.append(self.name, buf)
            self._r.rpush(self.name, buf)
        self._r.expire(self.name, self.expire_time)

    def read(self):
        # buf = self._r.get(self.name)
        buf_list = self._r.lrange(self.name, 0, -1)
        buf = b''.join(buf_list)
        data = np.frombuffer(buf,
                             dtype=self.dtype) if buf is not None else None
        return data

    @property
    def size(self):
        array = self.data
        if array is None:
            return 0
        else:
            return array.size

    @property
    def data(self):
        return self.read()
