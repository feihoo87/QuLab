import asyncio
import os
import pickle
import time
from pathlib import Path

import click
import dill
import zmq
from loguru import logger

from qulab.sys.rpc.zmq_socket import ZMQContextManager

from .curd import query_record, remove_tags, tag, update_tags
from .models import Record as RecordInDB
from .models import Session, create_engine, create_tables, sessionmaker, utcnow
from .record import Record

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
            record.database = datapath
            record._file = path
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


@logger.catch
async def handle(session: Session, request: Request, datapath: Path):

    msg = request.msg

    match request.method:
        case 'ping':
            await reply(request, 'pong')
        case 'bufferlist_slice':
            record = get_record(session, msg['record_id'], datapath)
            bufferlist = record.get(msg['key'],
                                    buffer_to_array=False,
                                    slice=msg['slice'])
            await reply(request, list(bufferlist.iter()))
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
