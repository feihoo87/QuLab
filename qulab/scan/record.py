import itertools
import lzma
import pickle
import sys
import uuid
import zipfile
from pathlib import Path
from threading import Lock
from types import EllipsisType

import dill
import numpy as np
import zmq

from qulab.sys.rpc.zmq_socket import ZMQContextManager

from .curd import get_config
from .space import OptimizeSpace, Space

_not_given = object()


def random_path(base):
    while True:
        s = uuid.uuid4().hex
        path = base / s[:2] / s[2:4] / s[4:6] / s[6:]
        if not path.exists():
            return path


def index_in_slice(slice_obj: slice | int, index: int):
    if isinstance(slice_obj, int):
        return slice_obj == index
    start, stop, step = slice_obj.start, slice_obj.stop, slice_obj.step
    if start is None:
        start = 0
    if step is None:
        step = 1
    if stop is None:
        stop = sys.maxsize

    if step > 0:
        return start <= index < stop and (index - start) % step == 0
    else:
        return stop < index <= start and (index - start) % step == 0


class BufferList():

    def __init__(self, file=None, slice=None):
        self._list = []
        self.lu = ()
        self.rd = ()
        self.inner_shape = ()
        self.file = file
        self._slice = slice
        self._lock = Lock()
        self._data_id = None
        self._sock = None

    def __repr__(self):
        return f"<BufferList: shape={self.shape}, lu={self.lu}, rd={self.rd}, slice={self._slice}>"

    def __getstate__(self):
        self.flush()
        if isinstance(self.file, Path):
            file = '/'.join(self.file.parts[-4:])
        else:
            file = self.file
        return {
            'file': file,
            'lu': self.lu,
            'rd': self.rd,
            'inner_shape': self.inner_shape,
        }

    def __setstate__(self, state):
        self.file = state['file']
        self.lu = state['lu']
        self.rd = state['rd']
        self.inner_shape = state['inner_shape']
        self._list = []
        self._slice = None
        self._lock = Lock()
        self._data_id = None
        self._sock = None

    @property
    def shape(self):
        return tuple([i - j
                      for i, j in zip(self.rd, self.lu)]) + self.inner_shape

    def flush(self):
        if not self._list:
            return
        if isinstance(self.file, Path):
            with self._lock:
                with open(self.file, 'ab') as f:
                    for item in self._list:
                        dill.dump(item, f)
                self._list.clear()

    def delete(self):
        if isinstance(self.file, Path):
            self.file.unlink()
            self.file = None

    def append(self, pos, value, dims=None):
        if dims is not None:
            if any([p != 0 for i, p in enumerate(pos) if i not in dims]):
                return
            pos = tuple([pos[i] for i in dims])
        self.lu = tuple([min(i, j) for i, j in zip(pos, self.lu)])
        self.rd = tuple([max(i + 1, j) for i, j in zip(pos, self.rd)])
        if hasattr(value, 'shape'):
            if self.inner_shape is None:
                self.inner_shape = value.shape
            elif self.inner_shape != value.shape:
                self.inner_shape = ()
        with self._lock:
            self._list.append((pos, value))
        if len(self._list) > 1000:
            self.flush()

    def _iter_file(self):
        if isinstance(self.file, Path) and self.file.exists():
            with self._lock:
                with open(self.file, 'rb') as f:
                    while True:
                        try:
                            pos, value = dill.load(f)
                            yield pos, value
                        except EOFError:
                            break
        elif isinstance(
                self.file, tuple) and len(self.file) == 2 and isinstance(
                    self.file[0], str) and self.file[0].endswith('.zip'):
            f, name = self.file
            with zipfile.ZipFile(f, 'r') as z:
                with z.open(name, 'r') as f:
                    while True:
                        try:
                            pos, value = dill.load(f)
                            yield pos, value
                        except EOFError:
                            break

    def iter(self):
        if self._data_id is None:
            for pos, value in itertools.chain(self._iter_file(), self._list):
                if not self._slice:
                    yield pos, value
                elif all(
                    [index_in_slice(s, i) for s, i in zip(self._slice, pos)]):
                    if self.inner_shape:
                        yield pos, value[self._slice[len(pos):]]
                    else:
                        yield pos, value
        else:
            server, record_id, key = self._data_id
            with ZMQContextManager(zmq.DEALER,
                                   connect=server,
                                   socket=self._sock) as socket:
                iter_id = b''
                start = 0
                try:
                    while True:
                        socket.send_pyobj({
                            'method': 'bufferlist_iter',
                            'record_id': record_id,
                            'iter_id': iter_id,
                            'key': key,
                            'slice': self._slice,
                            'start': start
                        })
                        iter_id, lst, finished = socket.recv_pyobj()
                        start += len(lst)
                        yield from lst
                        if finished:
                            break
                finally:
                    if iter_id:
                        socket.send_pyobj({
                            'method': 'bufferlist_iter_exit',
                            'iter_id': iter_id
                        })

    def value(self):
        d = []
        for pos, value in self.iter():
            d.append(value)
        return d

    def pos(self):
        p = []
        for pos, value in self.iter():
            p.append(pos)
        return p

    def items(self):
        p, d = [], []
        for pos, value in self.iter():
            p.append(pos)
            d.append(value)
        return p, d

    def toarray(self):
        pos, data = self.items()
        if self._slice:
            pos = np.asarray(pos)
            lu = tuple(np.min(pos, axis=0))
            rd = tuple(np.max(pos, axis=0) + 1)
            pos = np.asarray(pos) - np.asarray(lu)
            shape = []
            for k, (s, i, j) in enumerate(zip(self._slice, rd, lu)):
                if s.step is not None:
                    pos[:, k] = pos[:, k] / s.step
                    shape.append(round(np.ceil((i - j) / s.step)))
                else:
                    shape.append(i - j)
            shape = tuple(shape)
        else:
            shape = tuple([i - j for i, j in zip(self.rd, self.lu)])
            pos = np.asarray(pos) - np.asarray(self.lu)
        data = np.asarray(data)
        inner_shape = data.shape[1:]
        x = np.full(shape + inner_shape, np.nan, dtype=data[0].dtype)
        x.__setitem__(tuple(pos.T), data)
        return x

    def _full_slice(self, slice_tuple: slice
                    | tuple[slice | int | EllipsisType, ...]):
        ndim = len(self.lu)
        if self.inner_shape:
            ndim += len(self.inner_shape)

        if isinstance(slice_tuple, slice):
            slice_tuple = (
                slice_tuple, ) + (slice(0, sys.maxsize, 1), ) * (ndim - 1)
        if slice_tuple is Ellipsis:
            slice_tuple = (slice(0, sys.maxsize, 1), ) * ndim
        else:
            head, tail = (), ()
            for i, s in enumerate(slice_tuple):
                if s is Ellipsis:
                    head = slice_tuple[:i]
                    tail = slice_tuple[i + 1:]
                    break
            else:
                head = slice_tuple
                tail = ()
            slice_tuple = head + (slice(
                0, sys.maxsize, 1), ) * (ndim - len(head) - len(tail)) + tail
        slice_list = []
        contract = []
        reversed = []
        for i, s in enumerate(slice_tuple):
            if isinstance(s, int):
                if s >= 0:
                    slice_list.append(slice(s, s + 1, 1))
                elif i < len(self.lu):
                    s = self.rd[i] + s
                    slice_list.append(slice(s, s + 1, 1))
                else:
                    slice_list.append(slice(s, s - 1, -1))
                contract.append(i)
            else:
                start, stop, step = s.start, s.stop, s.step
                if step is None:
                    step = 1
                if step < 0 and i < len(self.lu):
                    step = -step
                    reversed.append(i)
                    if start is None and stop is None:
                        start, stop = 0, sys.maxsize
                    elif start is None:
                        start, stop = self.lu[i], sys.maxsize
                    elif stop is None:
                        start, stop = 0, start + self.lu[i]
                    else:
                        start, stop = stop + self.lu[i] + 1, start + self.lu[
                            i] + 1

                if start is None:
                    start = 0
                elif start < 0 and i < len(self.lu):
                    start = self.rd[i] + start
                if step is None:
                    step = 1
                if stop is None:
                    stop = sys.maxsize
                elif stop < 0 and i < len(self.lu):
                    stop = self.rd[i] + stop

                slice_list.append(slice(start, stop, step))
        return tuple(slice_list), contract, reversed

    def __getitem__(self, slice_tuple: slice | EllipsisType
                    | tuple[slice | int | EllipsisType, ...]):
        self._slice, contract, reversed = self._full_slice(slice_tuple)
        ret = self.toarray()
        slices = []
        for i, s in enumerate(self._slice):
            if i in contract:
                slices.append(0)
            elif isinstance(s, slice):
                if i in reversed:
                    slices.append(slice(None, None, -1))
                else:
                    slices.append(slice(None, None, 1))
        ret = ret.__getitem__(tuple(slices))
        self._slice = None
        return ret


class Record():

    def __init__(self, id, database, description=None):
        self.id = id
        self.database = database
        self.description = description
        self._items = {}
        self._pos = []
        self._last_vars = set()
        self._file = None
        self._sock = None

        for name, value in self.description['intrinsic_loops'].items():
            self._items[name] = value

        for level, range_list in description['loops'].items():
            for name, iterable in range_list:
                if name in self.description['independent_variables']:
                    self._items[name] = iterable

        if self.is_local_record():
            self.database = Path(self.database)
            self._file = random_path(self.database / 'objects')
            self._file.parent.mkdir(parents=True, exist_ok=True)

    def __getstate__(self) -> dict:
        return {
            'id': self.id,
            'description': self.description,
            '_items': self._items,
        }

    def __setstate__(self, state: dict):
        self.id = state['id']
        self.description = state['description']
        self._items = state['_items']
        self._pos = []
        self._last_vars = set()
        self.database = None
        self._file = None
        self._sock = None

    @property
    def axis(self):
        return self.description.get('axis', {})

    def config(self, cls=dict, session=None, datapath=None):
        config_id = self.description.get('config', None)
        if config_id is None:
            return None
        if isinstance(config_id, dict):
            return cls(config_id)
        if self.is_remote_record():
            with ZMQContextManager(zmq.DEALER,
                                   connect=self.database,
                                   socket=self._sock) as socket:
                socket.send_pyobj({
                    'method': 'config_get',
                    'config_id': config_id
                })
                buf = socket.recv_pyobj()
                return cls(pickle.loads(lzma.decompress(buf)))
        else:
            assert session is not None, "session is required for local record"
            assert datapath is not None, "datapath is required for local record"
            config = get_config(session, config_id, base=datapath / 'objects')
            session.commit()
            return cls(config)

    def scripts(self, session=None):
        scripts = self.description['entry']['scripts']
        if isinstance(scripts, list):
            return scripts
        else:
            cell_id = scripts

        if self.is_remote_record():
            with ZMQContextManager(zmq.DEALER,
                                   connect=self.database,
                                   socket=self._sock) as socket:
                socket.send_pyobj({
                    'method': 'notebook_history',
                    'cell_id': cell_id
                })
                return socket.recv_pyobj()
        elif self.is_local_record():
            from .models import Cell
            assert session is not None, "session is required for local record"
            cell = session.get(Cell, cell_id)
            return [
                cell.input.text
                for cell in cell.notebook.cells[1:cell.index + 2]
            ]

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
        return self.get(key, buffer_to_array=True)

    def get(self, key, default=_not_given, buffer_to_array=False):
        if self.is_remote_record():
            with ZMQContextManager(zmq.DEALER,
                                   connect=self.database,
                                   socket=self._sock) as socket:
                socket.send_pyobj({
                    'method': 'record_getitem',
                    'record_id': self.id,
                    'key': key
                })
                ret = socket.recv_pyobj()
                if isinstance(ret, BufferList):
                    ret._data_id = self.database, self.id, key
                    ret._sock = socket
                    if buffer_to_array:
                        return ret.toarray()
                    else:
                        return ret
                elif isinstance(ret, Space) and buffer_to_array:
                    return ret.toarray()
                else:
                    return ret
        else:
            if default is _not_given:
                d = self._items.get(key)
            else:
                d = self._items.get(key, default)
            if isinstance(d, BufferList):
                if isinstance(d.file, str):
                    d.file = self._file.parent.parent.parent.parent / d.file
                if buffer_to_array:
                    return d.toarray()
                else:
                    return d
            elif isinstance(d, Space):
                if buffer_to_array:
                    return d.toarray()
                else:
                    return d
            else:
                return d

    def keys(self):
        if self.is_remote_record():
            with ZMQContextManager(zmq.DEALER,
                                   connect=self.database,
                                   socket=self._sock) as socket:
                socket.send_pyobj({
                    'method': 'record_keys',
                    'record_id': self.id
                })
                keys = socket.recv_pyobj()
                self._items = {key: None for key in keys}
                return keys
        else:
            return list(self._items.keys())

    def append(self, level, step, position, variables):
        if level < 0:
            self.flush()
            return

        for key in set(variables.keys()) - self._last_vars:
            if key not in self.axis:
                self.axis[key] = tuple(range(level + 1))

        self._last_vars = set(variables.keys())

        if level >= len(self._pos):
            l = level + 1 - len(self._pos)
            self._pos.extend(([0] * (l - 1)) + [position])
            pos = tuple(self._pos)
        elif level == len(self._pos) - 1:
            self._pos[-1] = position
            pos = tuple(self._pos)
        else:
            self._pos = self._pos[:level + 1]
            self._pos[-1] = position
            pos = tuple(self._pos)
            self._pos[-1] += 1

        for key, value in variables.items():
            if self.axis[key] == ():
                if key not in self._items:
                    self._items[key] = value
            elif level == self.axis[key][-1]:
                if key not in self._items:
                    if self.is_local_record():
                        bufferlist_file = random_path(self.database /
                                                      'objects')
                        bufferlist_file.parent.mkdir(parents=True,
                                                     exist_ok=True)
                        self._items[key] = BufferList(bufferlist_file)
                    else:
                        self._items[key] = BufferList()
                    self._items[key].lu = pos
                    self._items[key].rd = tuple([i + 1 for i in pos])
                    self._items[key].append(pos, value, self.axis[key])
                elif isinstance(self._items[key], BufferList):
                    self._items[key].append(pos, value, self.axis[key])

    def flush(self):
        if self.is_remote_record() or self.is_cache_record():
            return

        for key, value in self._items.items():
            if isinstance(value, BufferList):
                value.flush()

        with open(self._file, 'wb') as f:
            dill.dump(self, f)

    def delete(self):
        if self.is_remote_record():
            with ZMQContextManager(zmq.DEALER,
                                   connect=self.database,
                                   socket=self._sock) as socket:
                socket.send_pyobj({
                    'method': 'record_delete',
                    'record_id': self.id
                })
        elif self.is_local_record():
            for key, value in self._items.items():
                if isinstance(value, BufferList):
                    value.delete()
            self._file.unlink()

    def export(self, file):
        with zipfile.ZipFile(file,
                             'w',
                             compression=zipfile.ZIP_DEFLATED,
                             compresslevel=9) as z:
            items = {}
            for key in self.keys():
                value = self.get(key)
                if isinstance(value, BufferList):
                    v = BufferList()
                    v.lu = value.lu
                    v.rd = value.rd
                    v.inner_shape = value.inner_shape
                    items[key] = v
                    with z.open(f'{key}.buf', 'w') as f:
                        for pos, data in value.iter():
                            dill.dump((pos, data), f)
                else:
                    items[key] = value
            with z.open('record.pkl', 'w') as f:
                self.description['entry']['scripts'] = self.scripts()
                dill.dump((self.description, items), f)
            with z.open('config.pkl', 'w') as f:
                f.write(dill.dumps(self.config()))

    @classmethod
    def load(cls, file: str):
        with zipfile.ZipFile(file, 'r') as z:
            with z.open('record.pkl', 'r') as f:
                description, items = dill.load(f)
            with z.open('config.pkl', 'r') as f:
                config = dill.load(f)
            description['config'] = config
            record = cls(None, None, description)
            for key, value in items.items():
                if isinstance(value, BufferList):
                    value.file = file, f'{key}.buf'
                record._items[key] = value
        return record

    def __repr__(self):
        if self.is_remote_record() and not self._items:
            self._items = {key: None for key in self.keys()}
        return f"<Record: id={self.id} app={self.description['app']}, keys={self._items.keys()}>"

    # def _repr_html_(self):
    #     return f"""
    #     <h3>Record: id={self.id}, app={self.description['app']}</h3>
    #     <p>keys={self.keys()}</p>
    #     <p>axis={self.axis}</p>
    #     """
