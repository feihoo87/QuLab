import asyncio
import os
import pickle
import time
import uuid
from pathlib import Path

import click
import dill
import zmq
from loguru import logger

from qulab.sys.rpc.zmq_socket import ZMQContextManager

from .curd import (create_cell, create_config, create_notebook, get_config,
                   query_record, remove_tags, tag, update_tags)
from .models import Cell, Notebook
from .models import Record as RecordInDB
from .models import Session, create_engine, create_tables, sessionmaker, utcnow
from .record import BufferList, Record, random_path

try:
    default_record_port = int(os.getenv('QULAB_RECORD_PORT', 6789))
except:
    default_record_port = 6789

if os.getenv('QULAB_RECORD_PATH'):
    datapath = Path(os.getenv('QULAB_RECORD_PATH'))
else:
    datapath = Path.home() / 'qulab' / 'data'
datapath.mkdir(parents=True, exist_ok=True)

namespace = uuid.uuid4()
record_cache = {}
buffer_list_cache = {}
CACHE_SIZE = 1024

pool = {}


class Request():
    __slots__ = ['sock', 'identity', 'msg', 'method']

    def __init__(self, sock, identity, msg):
        self.sock = sock
        self.identity = identity
        self.msg = pickle.loads(msg)
        self.method = self.msg.get('method', '')

    def __repr__(self):
        return f"Request({self.method})"


async def reply(req, resp):
    await req.sock.send_multipart([req.identity, pickle.dumps(resp)])


def clear_cache():
    if len(record_cache) < CACHE_SIZE:
        return

    for k, (t, _) in zip(sorted(record_cache.items(), key=lambda x: x[1][0]),
                         range(len(record_cache) - CACHE_SIZE)):
        del record_cache[k]

    for k, (t,
            _) in zip(sorted(buffer_list_cache.items(), key=lambda x: x[1][0]),
                      range(len(buffer_list_cache) - CACHE_SIZE)):
        del buffer_list_cache[k]


def flush_cache():
    for k, (t, r) in record_cache.items():
        r.flush()


def get_local_record(session: Session, id: int, datapath: Path) -> Record:
    record_in_db = session.get(RecordInDB, id)
    if record_in_db is None:
        return None
    record_in_db.atime = utcnow()

    if record_in_db.file.endswith('.zip'):
        return Record.load(datapath / 'objects' / record_in_db.file)

    path = datapath / 'objects' / record_in_db.file
    with open(path, 'rb') as f:
        record = dill.load(f)
        record.database = datapath
        record._file = path
    return record


def get_record(session: Session, id: int, datapath: Path) -> Record:
    if id not in record_cache:
        record = get_local_record(session, id, datapath)
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
    record_in_db.config_id = description['config']
    record._file = datapath / 'objects' / record_in_db.file
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


def record_delete(session: Session, record_id: int, datapath: Path):
    record = get_local_record(session, record_id, datapath)
    record.delete()
    record_in_db = session.get(RecordInDB, record_id)
    session.delete(record_in_db)
    session.commit()


@logger.catch
async def handle(session: Session, request: Request, datapath: Path):

    msg = request.msg

    match request.method:
        case 'ping':
            await reply(request, 'pong')
        case 'bufferlist_iter':
            if msg['iter_id'] in buffer_list_cache:
                it = buffer_list_cache[msg['iter_id']][1]
                iter_id = msg['iter_id']
            else:
                iter_id = uuid.uuid3(namespace, str(time.time_ns())).bytes
                record = get_record(session, msg['record_id'], datapath)
                bufferlist = record.get(msg['key'],
                                        buffer_to_array=False,
                                        slice=msg['slice'])
                it = bufferlist.iter()
                for _, _ in zip(range(msg['start']), it):
                    pass
            current_time = time.time()
            ret, end = [], False
            while time.time() - current_time < 0.02:
                try:
                    ret.append(next(it))
                except StopIteration:
                    end = True
                    break
            await reply(request, (iter_id, ret, end))
            buffer_list_cache[iter_id] = time.time(), it
            clear_cache()
        case 'bufferlist_iter_exit':
            try:
                it = buffer_list_cache.pop(msg['iter_id'])[1]
                it.throw(Exception)
            except:
                pass
            clear_cache()
        case 'record_create':
            description = dill.loads(msg['description'])
            await reply(request, record_create(session, description, datapath))
        case 'record_append':
            record_append(session, msg['record_id'], msg['level'], msg['step'],
                          msg['position'], msg['variables'], datapath)
        case 'record_description':
            record = get_record(session, msg['record_id'], datapath)
            await reply(request, dill.dumps(record))
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
        case 'notebook_create':
            notebook = create_notebook(session, msg['name'])
            session.commit()
            await reply(request, notebook.id)
        case 'notebook_extend':
            notebook = session.get(Notebook, msg['notebook_id'])
            inputCells = msg.get('input_cells', [""])
            aready_saved = len(notebook.cells)
            if len(inputCells) > aready_saved:
                for cell in inputCells[aready_saved:]:
                    cell = create_cell(session, notebook, cell)
                session.commit()
                await reply(request, cell.id)
            else:
                await reply(request, None)
        case 'notebook_history':
            cell = session.get(Cell, msg['cell_id'])
            if cell:
                await reply(request, [
                    cell.input.text
                    for cell in cell.notebook.cells[1:cell.index + 2]
                ])
            else:
                await reply(request, None)
        case 'config_get':
            config = get_config(session,
                                msg['config_id'],
                                base=datapath / 'objects')
            session.commit()
            await reply(request, config)
        case 'config_update':
            config = create_config(session,
                                   msg['update'],
                                   base=datapath / 'objects',
                                   filename='/'.join(
                                       random_path(datapath /
                                                   'objects').parts[-4:]))
            session.commit()
            await reply(request, config.id)
        case 'submit':
            from .scan import Scan
            finished = [(id, queried) for id, (task, queried) in pool.items()
                        if not isinstance(task, int) and task.finished()]
            for id, queried in finished:
                if not queried:
                    pool[id] = [pool[id].record.id, False]
                else:
                    pool.pop(id)
            description = dill.loads(msg['description'])
            task = Scan()
            task.description = description
            task.start()
            pool[task.id] = [task, False]
            await reply(request, task.id)
        case 'get_record_id':
            task, queried = pool.get(msg['id'])
            if isinstance(task, int):
                await reply(request, task)
                pool.pop(msg['id'])
            else:
                for _ in range(10):
                    if task.record:
                        await reply(request, task.record.id)
                        pool[msg['id']] = [task, True]
                        break
                    await asyncio.sleep(1)
                else:
                    await reply(request, None)
        case _:
            logger.error(f"Unknown method: {msg['method']}")


async def handle_with_timeout(session: Session, request: Request,
                              datapath: Path, timeout: float):
    try:
        await asyncio.wait_for(handle(session, request, datapath),
                               timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(
            f"Task handling request {request} timed out and was cancelled.")
        await reply(request, 'timeout')
    except Exception as e:
        await reply(request, f'{e!r}')


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
                asyncio.create_task(
                    handle_with_timeout(session, req, datapath, timeout=60.0))
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
def server(port, datapath, url, timeout, buffer, interval):
    asyncio.run(main(port, Path(datapath), url, timeout, buffer, interval))


if __name__ == "__main__":
    server()
