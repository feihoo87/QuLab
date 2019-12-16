import time
import pickle
import math
import io
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from functools import reduce

from qulab import config

from ..schema.record import Record as mongoRecord

'''把redisRecord实例存为其他格式的后端集合，
需要实例redis_record和模式mode两个参数，存储后返回存储路径或者数据库ID等唯一识别码'''

__storage_cfg = config.get('storage', {})

def get_filepath(name):
    '''根据配置文件和一个参数name获取存储的路径和文件名'''
    base_path = Path(__storage_cfg.get('data_path', Path.cwd()))
    path = base_path / time.strftime('%Y') / time.strftime('%m%d')
    path.mkdir(parents=True, exist_ok=True)
    fname_raw=f"{name}_{time.strftime('%Y%m%d%H%M%S')}"
    return path,fname_raw

def npz(redis_record,mode=None):
    '''npz 后端'''
    path,fname_raw=get_filepath(redis_record.name)
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

def dat(redis_record,mode=None):
    '''dat 后端'''
    path,fname_raw=get_filepath(redis_record.name)
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

def mongo(redis_record,mode=None):
    '''mongoDB 后端'''
    record = mongoRecord(title=redis_record.name,
            config=redis_record.config,
            setting=redis_record.setting,
            tags=redis_record.tags)
    record.set_data(redis_record.data)
    fig=gen_fig(redis_record)
    buff = io.BytesIO()
    fig.savefig(buff, format='png')
    img = buff.getvalue()
    record.set_image(img)
    record.save()
    return str(record.id)

def gen_fig(redis_record):
    '''画图函数，由redis记录产生一个matplotlib的图片'''
    dim = redis_record.collector.dim
    zshape = redis_record.collector.zshape
    zsize = reduce(lambda a,b:a*b, zshape)
    datashape=redis_record.collector.shape
    datashape_r=(*datashape[:dim],zsize)
    if zsize<4:
        plot_shape=(1,zsize)
    else:
        n=int(np.sqrt(zsize))
        plot_shape=(math.ceil(zsize/n),n)
    figsize=plot_shape[1]*8,plot_shape[0]*6
    fig,axis=plt.subplots(*plot_shape,figsize=figsize)
    axis=np.array(axis).flatten()
    if dim==1:
        x,z=redis_record.data
        z=z.reshape(datashape_r)
        z=np.abs(z) if np.any(np.iscomplex(z)) else z
        for i in range(zsize):
            axis[i].plot(x,z[:,i])
            title=f'{redis_record.name} {i}' if i>0 else f'{redis_record.name}'
            axis[i].set_title(title)
    elif dim==2:
        x,y,z=redis_record.data
        z=z.reshape(datashape_r)
        z=np.abs(z) if np.any(np.iscomplex(z)) else z
        for i in range(zsize):
            axis[i].imshow(z[:,:,i],
                        extent=(y[0], y[-1], x[0], x[-1]),
                        origin='lower',
                        aspect='auto')
            title=f'{redis_record.name} {i}' if i>0 else f'{redis_record.name}'
            axis[i].set_title(title)
    else:
        pass
    return fig

def fig(redis_record,mode='jpg'):
    '''一个保存成图片的后端
    Parameter:
        redis_record: 本模块中redisRecord的一个实例
        mode: 模式，这里是保存成图片的后缀名，为matplotlib支持的保存格式，比如: jpg,pdf,svg等
    Return:
        图片的保存路径
    '''
    path,fname_raw=get_filepath(redis_record.name)
    fname = f"{fname_raw}.{mode}"
    fig = gen_fig(redis_record)
    fig.savefig(path / fname)
    print(path / fname)
    return path / fname