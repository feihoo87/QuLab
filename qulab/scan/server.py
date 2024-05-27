import asyncio
import pickle
import sys
import time
import uuid
from pathlib import Path
from .scan import Scan
import click
import dill
import numpy as np
import zmq
from loguru import logger

from qulab.sys.rpc.zmq_socket import ZMQContextManager

pool = {}

class Request():
    __slots__ = ['sock', 'identity', 'msg', 'method']

    def __init__(self, sock, identity, msg):
        self.sock = sock
        self.identity = identity
        self.msg = pickle.loads(msg)
        self.method = self.msg.get('method', '')


async def reply(req, resp):
    await req.sock.send_multipart([req.identity, pickle.dumps(resp)])


@logger.catch
async def handle(request: Request):

    msg = request.msg

    match request.method:
        case 'ping':
            await reply(request, 'pong')
        case 'submit':
            description = dill.loads(msg['description'])
            task = Scan()
            task.description = description
            task.start()
            pool[task.id] = task
            await reply(request, task.id)
        case 'get_record_id':
            task = pool.get(msg['id'])
            for _ in range(10):
                if task.record:
                    await reply(request, task.record.id)
                    break
                await asyncio.sleep(1)
            else:
                await reply(request, None)
        case _:
            logger.error(f"Unknown method: {msg['method']}")


async def _handle(request: Request):
    try:
        await handle(request)
    except:
        await reply(request, 'error')


async def serv(port):
    logger.info('Server starting.')
    async with ZMQContextManager(zmq.ROUTER, bind=f"tcp://*:{port}") as sock:
        logger.info('Server started.')
        while True:
            identity, msg = await sock.recv_multipart()
            req = Request(sock, identity, msg)
            asyncio.create_task(_handle(req))


async def watch(port, timeout=1):
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
                return asyncio.create_task(serv(port))
            await asyncio.sleep(timeout)


async def main(port, timeout=1):
    task = await watch(port=port, timeout=timeout)
    await task


@click.command()
@click.option('--port', default=6788, help='Port of the server.')
@click.option('--timeout', default=1, help='Timeout of ping.')
def server(port, timeout):
    asyncio.run(main(port, timeout))


if __name__ == "__main__":
    server()
