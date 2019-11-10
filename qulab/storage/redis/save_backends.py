import time
import pickle
import numpy as np
from pathlib import Path

from qulab import config


'''把redisRecord实例存为其他格式的后端集合，
需要以一个实例redis_record作为参数，存储后返回存储路径或者数据库ID等唯一识别码'''

__storage_cfg = config.get('storage', {})

def __get_filepath(name):
    base_path = Path(__storage_cfg.get('data_path', Path.cwd()))
    path = base_path / time.strftime('%Y') / time.strftime('%m%d')
    path.mkdir(parents=True, exist_ok=True)
    fname_raw=f"{name}_{time.strftime('%Y%m%d%H%M%S')}"
    return path,fname_raw

def npz(redis_record):
    path,fname_raw=__get_filepath(redis_record.name)
    fname = f"{fname_raw}.npz"
    args=redis_record.data
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
    return path / fname

def dat(redis_record):
    path,fname_raw=__get_filepath(redis_record.name)
    fname = f"{fname_raw}.dat"

    record = dict(
                config=redis_record.config,
                setting=redis_record.setting,
                tags=redis_record.tags,
                data=redis_record.data
            )
    record_b=pickle.dumps(record)
            
    with open(path / fname,'wb') as f:
        f.write(record_b)
    print(path / fname)
    return path / fname

def mongo(redis_record):
    return