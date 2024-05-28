import asyncio
import os
import pickle
import sys
import time
import uuid
from collections import defaultdict
from pathlib import Path
from threading import Lock

import click
import dill
import numpy as np
import zmq
from loguru import logger

from qulab.sys.rpc.zmq_socket import ZMQContextManager

from .curd import query_record, remove_tags, tag, update_tags
from .models import Record as RecordInDB
from .models import Session, create_engine, create_tables, sessionmaker, utcnow

_notgiven = object()

try:
    default_record_port = int(os.getenv('QULAB_RECORD_PORT', 6789))
except:
    default_record_port = 6789

if os.getenv('QULAB_RECORD_PATH'):
    datapath = Path(os.getenv('QULAB_RECORD_PATH'))
else:
    datapath = Path.home() / 'qulab' / 'data'
datapath.mkdir(parents=True, exist_ok=True)

record_cache = {}


def random_path(base):
    while True:
        s = uuid.uuid4().hex
        path = base / s[:2] / s[2:4] / s[4:6] / s[6:]
        if not path.exists():
            return path


class BufferList():

    def __init__(self, pos_file=None, value_file=None):
        self._pos = []
        self._value = []
        self.lu = ()
        self.rd = ()
        self.pos_file = pos_file
        self.value_file = value_file
        self._lock = Lock()

    def __getstate__(self):
        return {
            'pos_file': self.pos_file,
            'value_file': self.value_file,
            '_pos': self._pos,
            '_value': self._value,
            'lu': self.lu,
            'rd': self.rd
        }

    def __setstate__(self, state):
        self.pos_file = state['pos_file']
        self.value_file = state['value_file']
        self._pos = state['_pos']
        self._value = state['_value']
        self.lu = state['lu']
        self.rd = state['rd']
        self._lock = Lock()

    @property
    def shape(self):
        return tuple([i - j for i, j in zip(self.rd, self.lu)])

    def flush(self):
        with self._lock:
            if self.pos_file is not None:
                with open(self.pos_file, 'ab') as f:
                    for pos in self._pos:
                        dill.dump(pos, f)
                self._pos.clear()
            if self.value_file is not None:
                with open(self.value_file, 'ab') as f:
                    for value in self._value:
                        dill.dump(value, f)
                self._value.clear()

    def append(self, pos, value, dims=None):
        if dims is not None:
            if any([p != 0 for i, p in enumerate(pos) if i not in dims]):
                return
            pos = tuple([pos[i] for i in dims])
        self.lu = tuple([min(i, j) for i, j in zip(pos, self.lu)])
        self.rd = tuple([max(i + 1, j) for i, j in zip(pos, self.rd)])
        self._pos.append(pos)
        self._value.append(value)
        if len(self._value) > 1000:
            self.flush()

    def value(self):
        v = []
        if self.value_file is not None and self.value_file.exists():
            with self._lock:
                with open(self.value_file, 'rb') as f:
                    while True:
                        try:
                            v.append(dill.load(f))
                        except EOFError:
                            break
        v.extend(self._value)
        return v

    def pos(self):
        p = []
        if self.pos_file is not None and self.pos_file.exists():
            with self._lock:
                with open(self.pos_file, 'rb') as f:
                    while True:
                        try:
                            p.append(dill.load(f))
                        except EOFError:
                            break
        p.extend(self._pos)
        return p

    def array(self):
        pos = np.asarray(self.pos()) - np.asarray(self.lu)
        data = np.asarray(self.value())
        inner_shape = data.shape[1:]
        x = np.full(self.shape + inner_shape, np.nan, dtype=data[0].dtype)
        x.__setitem__(tuple(pos.T), data)
        return x


class Record():

    def __init__(self, id, database, description=None):
        self.id = id
        self.database = database
        self.description = description
        self._keys = set()
        self._items = {}
        self._index = []
        self._pos = []
        self._last_vars = set()
        self._levels = {}
        self._file = None
        self.independent_variables = {}
        self.constants = {}
        self.dims = {}

        for name, value in self.description['consts'].items():
            if name not in self._items:
                self._items[name] = value
            self.constants[name] = value
            self.dims[name] = ()
        for level, range_list in self.description['loops'].items():
            for name, iterable in range_list:
                if isinstance(iterable, (np.ndarray, list, tuple, range)):
                    self._items[name] = iterable
                    self.independent_variables[name] = iterable
                    self.dims[name] = (level, )

        for level, group in self.description['order'].items():
            for names in group:
                for name in names:
                    self._levels[name] = level
                    if name not in self.dims:
                        if name not in self.description['dependents']:
                            self.dims[name] = (level, )
                        else:
                            d = set()
                            for n in self.description['dependents'][name]:
                                d.update(self.dims[n])
                            self.dims[name] = tuple(sorted(d))

        if self.is_local_record():
            self.database = Path(self.database)
            self._file = random_path(self.database / 'objects')
            self._file.parent.mkdir(parents=True, exist_ok=True)

    def is_local_record(self):
        return not self.is_cache_record() and not self.is_remote_record()

    def is_cache_record(self):
        return self.database is None

    def is_remote_record(self):
        return isinstance(self.database,
                          str) and self.database.startswith("tcp://")

    def __del__(self):
        self.flush()

    def __getitem__(self, key):
        return self.get(key)

    def get(self, key, default=_notgiven, buffer_to_array=True):
        if self.is_remote_record():
            with ZMQContextManager(zmq.DEALER,
                                   connect=self.database) as socket:
                socket.send_pyobj({
                    'method': 'record_getitem',
                    'record_id': self.id,
                    'key': key
                })
                ret = socket.recv_pyobj()
                if isinstance(ret, BufferList) and buffer_to_array:
                    return ret.array()
                else:
                    return ret
        else:
            if default is _notgiven:
                d = self._items.get(key)
            else:
                d = self._items.get(key, default)
            if isinstance(d, BufferList):
                if buffer_to_array:
                    return d.array()
                else:
                    ret = BufferList()
                    ret._pos = d.pos()
                    ret._value = d.value()
                    ret.lu = d.lu
                    ret.rd = d.rd
                    return ret
            else:
                return d

    def keys(self):
        if self.is_remote_record():
            with ZMQContextManager(zmq.DEALER,
                                   connect=self.database) as socket:
                socket.send_pyobj({
                    'method': 'record_keys',
                    'record_id': self.id
                })
                return socket.recv_pyobj()
        else:
            return list(self._keys)

    def append(self, level, step, position, variables):
        if level < 0:
            self.flush()
            return

        for key in set(variables.keys()) - self._last_vars:
            if key not in self._levels:
                self._levels[key] = level
                self.dims[key] = tuple(range(level + 1))

        self._last_vars = set(variables.keys())
        self._keys.update(variables.keys())

        if level >= len(self._pos):
            l = level + 1 - len(self._pos)
            self._index.extend(([0] * (l - 1)) + [step])
            self._pos.extend(([0] * (l - 1)) + [position])
            pos = tuple(self._pos)
        elif level == len(self._pos) - 1:
            self._index[-1] = step
            self._pos[-1] = position
            pos = tuple(self._pos)
        else:
            self._index = self._index[:level + 1]
            self._pos = self._pos[:level + 1]
            self._index[-1] = step + 1
            self._pos[-1] = position
            pos = tuple(self._pos)
            self._pos[-1] += 1

        for key, value in variables.items():
            if level == self._levels[key]:
                if key not in self._items:
                    if self.is_local_record():
                        f1 = random_path(self.database / 'objects')
                        f1.parent.mkdir(parents=True, exist_ok=True)
                        f2 = random_path(self.database / 'objects')
                        f2.parent.mkdir(parents=True, exist_ok=True)
                        self._items[key] = BufferList(f1, f2)
                    else:
                        self._items[key] = BufferList()
                    self._items[key].lu = pos
                    self._items[key].rd = tuple([i + 1 for i in pos])
                    self._items[key].append(pos, value, self.dims[key])
                elif isinstance(self._items[key], BufferList):
                    self._items[key].append(pos, value, self.dims[key])
            elif self._levels[key] == -1 and key not in self._items:
                self._items[key] = value

    def flush(self):
        if self.is_remote_record() or self.is_cache_record():
            return

        for key, value in self._items.items():
            if isinstance(value, BufferList):
                value.flush()

        with open(self._file, 'wb') as f:
            dill.dump(self, f)


class Request():
    __slots__ = ['sock', 'identity', 'msg', 'method']

    def __init__(self, sock, identity, msg):
        self.sock = sock
        self.identity = identity
        self.msg = pickle.loads(msg)
        self.method = self.msg.get('method', '')


async def reply(req, resp):
    await req.sock.send_multipart([req.identity, pickle.dumps(resp)])


def clear_cache():
    if len(record_cache) < 1024:
        return

    for k, (t, _) in zip(sorted(record_cache.items(), key=lambda x: x[1][0]),
                         range(len(record_cache) - 1024)):
        del record_cache[k]


def flush_cache():
    for k, (t, r) in record_cache.items():
        r.flush()


def get_record(session: Session, id: int, datapath: Path) -> Record:
    if id not in record_cache:
        record_in_db = session.get(RecordInDB, id)
        record_in_db.atime = utcnow()
        path = datapath / 'objects' / record_in_db.file
        with open(path, 'rb') as f:
            record = dill.load(f)
    else:
        record = record_cache[id][1]
    clear_cache()
    record_cache[id] = time.time(), record
    return record


def record_create(session: Session, description: dict, datapath: Path) -> int:
    record = Record(None, datapath, description)
    record_in_db = RecordInDB()
    if 'app' in description:
        record_in_db.app = description['app']
    if 'tags' in description:
        record_in_db.tags = [tag(session, t) for t in description['tags']]
    record_in_db.file = '/'.join(record._file.parts[-4:])
    session.add(record_in_db)
    try:
        session.commit()
        record.id = record_in_db.id
        clear_cache()
        record_cache[record.id] = time.time(), record
        return record.id
    except:
        session.rollback()
        raise


def record_append(session: Session, record_id: int, level: int, step: int,
                  position: int, variables: dict, datapath: Path):
    record = get_record(session, record_id, datapath)
    record.append(level, step, position, variables)
    try:
        record_in_db = session.get(RecordInDB, record_id)
        record_in_db.mtime = utcnow()
        record_in_db.atime = utcnow()
        session.commit()
    except:
        session.rollback()
        raise


@logger.catch
async def handle(session: Session, request: Request, datapath: Path):

    msg = request.msg

    match request.method:
        case 'ping':
            await reply(request, 'pong')
        case 'record_create':
            description = dill.loads(msg['description'])
            await reply(request, record_create(session, description, datapath))
        case 'record_append':
            record_append(session, msg['record_id'], msg['level'], msg['step'],
                          msg['position'], msg['variables'], datapath)
        case 'record_description':
            record = get_record(session, msg['record_id'], datapath)
            await reply(request, dill.dumps(record.description))
        case 'record_getitem':
            record = get_record(session, msg['record_id'], datapath)
            await reply(request, record.get(msg['key'], buffer_to_array=False))
        case 'record_keys':
            record = get_record(session, msg['record_id'], datapath)
            await reply(request, record.keys())
        case 'record_query':
            total, apps, table = query_record(session,
                                              offset=msg.get('offset', 0),
                                              limit=msg.get('limit', 10),
                                              app=msg.get('app', None),
                                              tags=msg.get('tags', ()),
                                              before=msg.get('before', None),
                                              after=msg.get('after', None))
            await reply(request, (total, apps, table))
        case 'record_get_tags':
            record_in_db = session.get(RecordInDB, msg['record_id'])
            await reply(request, [t.name for t in record_in_db.tags])
        case 'record_remove_tags':
            remove_tags(session, msg['record_id'], msg['tags'])
        case 'record_add_tags':
            update_tags(session, msg['record_id'], msg['tags'], True)
        case 'record_replace_tags':
            update_tags(session, msg['record_id'], msg['tags'], False)
        case _:
            logger.error(f"Unknown method: {msg['method']}")


async def _handle(session: Session, request: Request, datapath: Path):
    try:
        await handle(session, request, datapath)
    except:
        await reply(request, 'error')


async def serv(port,
               datapath,
               url=None,
               buffer_size=1024 * 1024 * 1024,
               interval=60):
    logger.info('Server starting.')
    async with ZMQContextManager(zmq.ROUTER, bind=f"tcp://*:{port}") as sock:
        if url is None:
            url = 'sqlite:///' + str(datapath / 'data.db')
        engine = create_engine(url)
        create_tables(engine)
        Session = sessionmaker(engine)
        with Session() as session:
            logger.info('Server started.')
            received = 0
            last_flush_time = time.time()
            while True:
                identity, msg = await sock.recv_multipart()
                received += len(msg)
                req = Request(sock, identity, msg)
                asyncio.create_task(_handle(session, req, datapath))
                if received > buffer_size or time.time(
                ) - last_flush_time > interval:
                    flush_cache()
                    received = 0
                    last_flush_time = time.time()


async def watch(port, datapath, url=None, timeout=1, buffer=1024, interval=60):
    with ZMQContextManager(zmq.DEALER,
                           connect=f"tcp://127.0.0.1:{port}") as sock:
        sock.setsockopt(zmq.LINGER, 0)
        while True:
            try:
                sock.send_pyobj({"method": "ping"})
                if sock.poll(int(1000 * timeout)):
                    sock.recv()
                else:
                    raise asyncio.TimeoutError()
            except (zmq.error.ZMQError, asyncio.TimeoutError):
                return asyncio.create_task(
                    serv(port, datapath, url, buffer * 1024 * 1024, interval))
            await asyncio.sleep(timeout)


async def main(port, datapath, url, timeout=1, buffer=1024, interval=60):
    task = await watch(port=port,
                       datapath=datapath,
                       url=url,
                       timeout=timeout,
                       buffer=buffer,
                       interval=interval)
    await task


@click.command()
@click.option('--port',
              default=os.getenv('QULAB_RECORD_PORT', 6789),
              help='Port of the server.')
@click.option('--datapath', default=datapath, help='Path of the data.')
@click.option('--url', default=None, help='URL of the database.')
@click.option('--timeout', default=1, help='Timeout of ping.')
@click.option('--buffer', default=1024, help='Buffer size (MB).')
@click.option('--interval',
              default=60,
              help='Interval of flush cache, in unit of second.')
def record(port, datapath, url, timeout, buffer, interval):
    asyncio.run(main(port, Path(datapath), url, timeout, buffer, interval))


if __name__ == "__main__":
    record()
