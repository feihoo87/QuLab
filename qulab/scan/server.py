import asyncio
import os
import pickle
import subprocess
import sys
import time
import uuid
from pathlib import Path

import click
import dill
import zmq
from loguru import logger

from qulab.sys.rpc.zmq_socket import ZMQContextManager

from ..cli.config import get_config_value, log_options
from .curd import (create_cell, create_config, create_notebook, get_config,
                   query_record, remove_tags, tag, update_tags)
from .models import Cell, Notebook
from .models import Record as RecordInDB
from .models import Session, create_engine, create_tables, sessionmaker, utcnow
from .record import BufferList, Record, random_path
from .utils import dump_dict, load_dict

default_record_port = get_config_value('port',
                                       int,
                                       command_name='server',
                                       default=6789)

datapath = get_config_value('data',
                            Path,
                            command_name='server',
                            default=Path.home() / 'qulab' / 'data')

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


class Response():
    pass


class ErrorResponse(Response):

    def __init__(self, error):
        self.error = error


async def reply(req, resp):
    await req.sock.send_multipart([req.identity, pickle.dumps(resp)])


def clear_cache():
    if len(record_cache) < CACHE_SIZE:
        return

    logger.debug(f"clear_cache record_cache: {len(record_cache)}")
    for ((k, (t, r)),
         i) in zip(sorted(record_cache.items(), key=lambda x: x[1][0]),
                   range(len(record_cache) - CACHE_SIZE)):
        del record_cache[k]

    logger.debug(f"clear_cache buffer_list_cache: {len(buffer_list_cache)}")
    for ((k, (t, r)),
         i) in zip(sorted(buffer_list_cache.items(), key=lambda x: x[1][0]),
                   range(len(buffer_list_cache) - CACHE_SIZE)):
        del buffer_list_cache[k]
    logger.debug(f"clear_cache done.")


def flush_cache():
    logger.debug(f"flush_cache: {len(record_cache)}")
    for k, (t, r) in record_cache.items():
        r.flush()
    logger.debug(f"flush_cache done.")


def get_local_record(session: Session, id: int, datapath: Path) -> Record:
    logger.debug(f"get_local_record: {id}")
    record_in_db = session.get(RecordInDB, id)
    if record_in_db is None:
        logger.debug(f"record not found: {id=}")
        return None
    record_in_db.atime = utcnow()

    if record_in_db.file.endswith('.zip'):
        logger.debug(f"load record from zip: {record_in_db.file}")
        record = Record.load(datapath / 'objects' / record_in_db.file)
        logger.debug(f"load record from zip done.")
        return record

    path = datapath / 'objects' / record_in_db.file
    with open(path, 'rb') as f:
        logger.debug(f"load record from file: {path}")
        record = dill.load(f)
        logger.debug(f"load record from file done.")
        record.database = datapath
        record._file = path
    return record


def get_record(session: Session, id: int, datapath: Path) -> Record:
    if id not in record_cache:
        record = get_local_record(session, id, datapath)
    else:
        logger.debug(f"get_record from cache: {id=}")
        record = record_cache[id][1]
    clear_cache()
    logger.debug(f"update lru time for record cache: {id=}")
    if record:
        record_cache[id] = time.time(), record
    return record


def record_create(session: Session, description: dict, datapath: Path) -> int:
    logger.debug(f"record_create: {description['app']}")
    record = Record(None, datapath, description)
    record_in_db = RecordInDB()
    if 'app' in description:
        record_in_db.app = description['app']
    if 'tags' in description:
        record_in_db.tags = [tag(session, t) for t in description['tags']]
    record_in_db.file = '/'.join(record._file.parts[-4:])
    record_in_db.config_id = description['config']
    record._file = datapath / 'objects' / record_in_db.file
    logger.debug(f"record_create generate random file: {record_in_db.file}")
    session.add(record_in_db)
    try:
        session.commit()
        logger.debug(f"record_create commited: record.id={record_in_db.id}")
        record.id = record_in_db.id
        clear_cache()
        record_cache[record.id] = time.time(), record
        return record.id
    except:
        logger.debug(f"record_create rollback")
        session.rollback()
        raise


def record_append(session: Session, record_id: int, level: int, step: int,
                  position: int, variables: dict, datapath: Path):
    logger.debug(f"record_append: {record_id}")
    record = get_record(session, record_id, datapath)
    logger.debug(f"record_append: {record_id}, {level}, {step}, {position}")
    record.append(level, step, position, variables)
    logger.debug(f"record_append done.")
    try:
        logger.debug(f"record_append update SQL database.")
        record_in_db = session.get(RecordInDB, record_id)
        logger.debug(f"record_append get RecordInDB: {record_in_db}")
        record_in_db.mtime = utcnow()
        record_in_db.atime = utcnow()
        logger.debug(f"record_append update RecordInDB: {record_in_db}")
        session.commit()
        logger.debug(f"record_append commited.")
    except:
        logger.debug(f"record_append rollback.")
        session.rollback()
        raise


def record_delete(session: Session, record_id: int, datapath: Path):
    record = get_local_record(session, record_id, datapath)
    record.delete()
    record_in_db = session.get(RecordInDB, record_id)
    session.delete(record_in_db)
    session.commit()


@logger.catch(reraise=True)
async def handle(session: Session, request: Request, datapath: Path):

    msg = request.msg

    if request.method not in ['ping']:
        logger.debug(f"handle: {request.method}")

    match request.method:
        case 'ping':
            await reply(request, 'pong')
        case 'bufferlist_iter':
            logger.debug(f"bufferlist_iter: {msg}")
            if msg['iter_id'] and msg['iter_id'] in buffer_list_cache:
                it = buffer_list_cache[msg['iter_id']][1]
                iter_id = msg['iter_id']
            else:
                iter_id = uuid.uuid3(namespace, str(time.time_ns())).bytes
                record = get_record(session, msg['record_id'], datapath)
                bufferlist = record.get(msg['key'], buffer_to_array=False)
                if msg['slice']:
                    bufferlist._slice = msg['slice']
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
            logger.debug(f"bufferlist_iter: {iter_id}, {end}")
            await reply(request, (iter_id, ret, end))
            logger.debug(f"reply bufferlist_iter: {iter_id}, {end}")
            buffer_list_cache[iter_id] = time.time(), it
            clear_cache()
        case 'bufferlist_iter_exit':
            logger.debug(f"bufferlist_iter_exit: {msg}")
            try:
                it = buffer_list_cache.pop(msg['iter_id'])[1]
                it.throw(Exception)
            except:
                pass
            clear_cache()
            logger.debug(f"end bufferlist_iter_exit: {msg}")
        case 'record_create':
            logger.debug(f"record_create")
            description = load_dict(msg['description'])
            await reply(request, record_create(session, description, datapath))
            logger.debug(f"reply record_create")
        case 'record_append':
            logger.debug(f"record_append")
            record_append(session, msg['record_id'], msg['level'], msg['step'],
                          msg['position'], msg['variables'], datapath)
            logger.debug(f"reply record_append")
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
            try:
                aready_saved = len(notebook.cells)
            except:
                aready_saved = 0
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
        case 'task_submit':
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
        case 'task_get_record_id':
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
        case 'task_get_progress':
            task, _ = pool.get(msg['id'])
            if isinstance(task, int):
                await reply(request, 1)
            else:
                await reply(request,
                            [(bar.n, bar.total) for bar in task._bar.values()])
        case _:
            logger.error(f"Unknown method: {msg['method']}")

    if request.method not in ['ping']:
        logger.debug(f"finished handle: {request.method}")


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
        logger.error(f"Task handling request {request} failed: {e!r}")
        await reply(request, ErrorResponse(f'{e!r}'))
    logger.debug(f"Task handling request {request} finished.")


async def serv(port,
               datapath,
               url='',
               buffer_size=1024 * 1024 * 1024,
               interval=60):
    datapath.mkdir(parents=True, exist_ok=True)
    logger.debug('Creating socket...')
    async with ZMQContextManager(zmq.ROUTER, bind=f"tcp://*:{port}") as sock:
        logger.info(f'Server started at port {port}.')
        logger.info(f'Data path: {datapath}.')
        if not url or url == 'sqlite':
            url = 'sqlite:///' + str(datapath / 'data.db')
        engine = create_engine(url)
        create_tables(engine)
        Session = sessionmaker(engine)
        with Session() as session:
            logger.info(f'Database connected: {url}.')
            received = 0
            last_flush_time = time.time()
            while True:
                logger.debug('Waiting for request...')
                identity, msg = await sock.recv_multipart()
                logger.debug('Received request.')
                received += len(msg)
                try:
                    req = Request(sock, identity, msg)
                except Exception as e:
                    logger.exception('bad request')
                    await sock.send_multipart(
                        [identity,
                         pickle.dumps(ErrorResponse(f'{e!r}'))])
                    continue
                asyncio.create_task(
                    handle_with_timeout(session, req, datapath,
                                        timeout=3600.0))
                if received > buffer_size or time.time(
                ) - last_flush_time > interval:
                    flush_cache()
                    received = 0
                    last_flush_time = time.time()


async def main(port, datapath, url, buffer=1024, interval=60):
    logger.info('Server starting...')
    await serv(port, datapath, url, buffer * 1024 * 1024, interval)


@click.command()
@click.option('--port',
              default=get_config_value('port',
                                       int,
                                       command_name='server',
                                       default=6789),
              help='Port of the server.')
@click.option('--datapath',
              default=get_config_value('data',
                                       Path,
                                       command_name='server',
                                       default=Path.home() / 'qulab' / 'data'),
              help='Path of the data.')
@click.option('--url', default='sqlite', help='URL of the database.')
@click.option('--buffer', default=1024, help='Buffer size (MB).')
@click.option('--interval',
              default=60,
              help='Interval of flush cache, in unit of second.')
@log_options(command_name='server')
def server(port, datapath, url, buffer, interval):
    try:
        import uvloop
        uvloop.run(main(port, Path(datapath), url, buffer, interval))
    except ImportError:
        asyncio.run(main(port, Path(datapath), url, buffer, interval))


if __name__ == "__main__":
    server()
