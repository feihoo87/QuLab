import inspect
from concurrent.futures import Future
from pathlib import Path

import dill
import zmq

from qulab.sys.rpc.zmq_socket import ZMQContextManager

from .recorder import Record


def call_func_with_kwds(func, args, kwds, log=None):
    funcname = getattr(func, '__name__', repr(func))
    sig = inspect.signature(func)
    for p in sig.parameters.values():
        if p.kind == p.VAR_KEYWORD:
            return func(*args, **kwds)
    kw = {
        k: v
        for k, v in kwds.items()
        if k in list(sig.parameters.keys())[len(args):]
    }
    try:
        args = [
            arg.result() if isinstance(arg, Future) else arg for arg in args
        ]
        kw = {
            k: v.result() if isinstance(v, Future) else v
            for k, v in kw.items()
        }
        return func(*args, **kw)
    except:
        if log:
            log.exception(f'Call {funcname} with {args} and {kw}')
        raise
    finally:
        if log:
            log.debug(f'Call {funcname} with {args} and {kw}')


def try_to_call(x, args, kwds, log=None):
    if callable(x):
        return call_func_with_kwds(x, args, kwds, log)
    return x


def get_record(id, database='tcp://127.0.0.1:6789'):
    if isinstance(database, str) and database.startswith('tcp://'):
        with ZMQContextManager(zmq.DEALER, connect=database) as socket:
            socket.send_pyobj({
                'method': 'record_description',
                'record_id': id
            })
            d = dill.loads(socket.recv_pyobj())
            print(d.keys())
            return Record(id, database, d)
    else:
        from .models import Record as RecordInDB
        from .models import create_engine, sessionmaker

        db_file = Path(database) / 'data.db'
        engine = create_engine(f'sqlite:///{db_file}')
        Session = sessionmaker(bind=engine)
        with Session() as session:
            path = Path(database) / 'objects' / session.get(RecordInDB,
                                                            id).file
            with open(path, 'rb') as f:
                record = dill.load(f)
            return record
