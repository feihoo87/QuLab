import asyncio
import functools
import logging
import multiprocessing as mp
import uuid
from enum import Enum, auto
import re

class QSStatus(Enum):
    OK = auto()
    Error = auto()


class QSTask:
    __slots__ = ['id', 'kw']

    def __init__(self, **kw):
        self.id = uuid.uuid4()
        self.kw = kw


class QSControlSignal:
    pass


class QSResultFuture:
    __slots__ = ['task_id', 'body', 'status']

    def __init__(self, body, task_id, status=QSStatus.OK):
        self.task_id = task_id
        self.body = body
        self.status = status

    async def result(self):
        ret = []
        async for v in self:
            ret.append(v)
        return ret

    def __aiter__(self):
        if isinstance(self.body, mp.connection.Connection):
            return QSResultIter(self.body, self.task_id)
        else:
            raise Exception('QSResult.body is not Connection')


class EndOfResult:
    pass


class QSResultIter:
    def __init__(self, conn, id):
        self.conn = conn
        self.id = id

    async def getData(self):
        while True:
            if self.conn.poll():
                ret = self.conn.recv()
                break
            await asyncio.sleep(0.001)
        return ret

    async def __anext__(self):
        while True:
            ret = await self.getData()
            if ret[0] == self.id:
                break
            else:
                self.conn.send(ret)
        if isinstance(ret[1], EndOfResult):
            raise StopAsyncIteration
        elif isinstance(ret[1], QSError):
            raise ret[1].error
        else:
            return ret[1]


class QSError:
    def __init__(self, error):
        self.error = error


class QSWorker:
    def __init__(self, **kw):
        self.conn = None
        self.procces = None
        self._tasks = []

    def _make_procces(self):
        self.conn, conn = mp.Pipe()
        self.procces = mp.Process(target=self.run, args=(conn, ))

    def run(self, conn):
        self.initialize()
        current = None
        while True:
            if len(self._tasks) == 0 and current is None or conn.poll():
                data = conn.recv()
            else:
                data = None
            if isinstance(data, QSControlSignal):
                break
            elif isinstance(data, tuple):
                conn.send(data)
            elif data is not None:
                self._tasks.append(data)
            try:
                if current is None and len(self._tasks) != 0:
                    task = self._tasks.pop(0)
                    current = task.id, self.do(task)
                if current is not None:
                    try:
                        conn.send((current[0], next(current[1])))
                    except StopIteration:
                        conn.send((current[0], EndOfResult()))
                        current = None
            except Exception as e:
                if current is not None:
                    conn.send((current[0], QSError(e)))
                else:
                    conn.send(QSError(e))
            finally:
                pass
        self.finalize()

    def initialize(self):
        pass

    def finalize(self):
        pass

    def do(self, task):
        yield

    def apply(self, task):
        self.conn.send(task)
        return QSResultFuture(self.conn, task.id)

    def is_running(self):
        return self.procces is not None and self.procces.is_alive()

    def start(self):
        if self.procces is not None and self.procces.is_alive():
            return
        self._make_procces()
        self.procces.start()

    def stop(self):
        self.conn.send(QSControlSignal())

    def join(self):
        self.procces.join()

    def terminate(self):
        self.procces.terminate()


class QulabService:
    def __init__(self):
        self._workers = {}
        self._workerFactorys = []

    def register(self, pattern, workerFactory, options):
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        self._workerFactorys.append((pattern, workerFactory, options))

    def makeWorker(self, name):
        for pattern, workerFactory, options in self._workerFactorys:
            info = pattern.match(name)
            if info:
                options.update(info.groupdict())
                worker = workerFactory(**options)
                return worker
        else:
            raise Exception('No workerFactory found for %r' % name)

    def apply(self, worker_name, task):
        if worker_name not in self._workers.keys():
            self._workers[worker_name] = self.makeWorker(worker_name)
        worker = self._workers[worker_name]
        if not worker.is_running():
            worker.start()
        return worker.apply(task)

    def stop(self):
        for k,worker in self._workers.items():
            worker.stop()
        for k,worker in self._workers.items():
            worker.join()

    def terminate(self):
        for k,worker in self._workers.items():
            worker.terminate()


class QSInstrumentWorker(QSWorker):
    def __init__(self, addr, driver):
        super().__init__()
        self.addr = addr
        self.driver = driver

    def initialize(self):
        mod = importlib.import_module(self.driver)
        Driver = getattr(mod, 'Driver')
        self.ins = Driver(**info)
        self.ins.performOpen()

    def do(self, task):
        pass
