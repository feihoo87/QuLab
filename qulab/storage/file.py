import lzma
import pathlib

import dill
import numpy as np

MAGIC = b'wAvEDatA'

lzma_filters = [{
    'id': lzma.FILTER_LZMA2,
    'preset': 9 | lzma.PRESET_EXTREME,
}]

FORMAT_RAW = 1
FORMAT_XZ = 2


def _get_header(file):
    assert MAGIC == file.read(len(MAGIC)), 'Invalid file format'
    version = file.read(1)
    version = int.from_bytes(version, 'big', signed=False)
    file_format = file.read(1)
    file_format = int.from_bytes(file_format, 'big', signed=False)
    info_size = file.read(2)
    info_size = int.from_bytes(info_size, 'big', signed=False)
    header = lzma.decompress(file.read(info_size),
                             format=lzma.FORMAT_RAW,
                             filters=lzma_filters)
    info = dill.loads(header)
    return {'version': version, 'format': file_format, 'info': info}


def _make_header(header: dict):
    version = header.get('version', 1)
    file_format = header.get('format', 1)
    info = header.get('info', {})
    header = lzma.compress(dill.dumps(info),
                           format=lzma.FORMAT_RAW,
                           filters=lzma_filters)
    assert len(header) < 2**16, 'Header too large'
    version = version.to_bytes(1, 'big', signed=False)
    file_format = file_format.to_bytes(1, 'big', signed=False)
    info_size = len(header).to_bytes(2, 'big', signed=False)
    return MAGIC + version + file_format + info_size + header


class FakeLock():

    def __enter__(self):
        pass

    def __exit__(self, *args):
        pass

    async def __aenter__(self):
        pass

    async def __aexit__(self, *args):
        pass


class BaseFile():

    def __init__(self, path: str | pathlib.Path, lock=None):
        self.path = path
        self.lock = lock or FakeLock()

    def compress(self):
        with self.lock:
            self._compress()

    def decompress(self):
        with self.lock:
            self._decompress()

    def _compress(self):
        with open(self.path, 'rb+') as f:
            try:
                header = _get_header(f)
            except:
                return
            if header.get('format', FORMAT_RAW) == FORMAT_XZ:
                return
            header['format'] = FORMAT_XZ
            buffer = f.read()
            f.seek(0)
            f.write(_make_header(header))
            f.write(
                lzma.compress(buffer,
                              format=lzma.FORMAT_RAW,
                              filters=lzma_filters))
            f.truncate()

    def _decompress(self):
        with open(self.path, 'rb+') as f:
            try:
                header = _get_header(f)
            except:
                return
            if header.get('format', FORMAT_RAW) == FORMAT_RAW:
                return
            header['format'] = FORMAT_RAW
            buffer = lzma.decompress(f.read(),
                                     format=lzma.FORMAT_RAW,
                                     filters=lzma_filters)
            f.seek(0)
            f.write(_make_header(header))
            f.write(buffer)
            f.truncate()


class BinaryFile(BaseFile):

    def read(self):
        with self.lock:
            with open(self.path, 'rb') as f:
                header = _get_header(f)
                if header.get('format', FORMAT_RAW) == FORMAT_XZ:
                    return lzma.decompress(f.read(),
                                           format=lzma.FORMAT_RAW,
                                           filters=lzma_filters)
                else:
                    return f.read()

    def write(self, data: bytes):
        with self.lock:
            with open(self.path, 'wb') as f:
                f.write(
                    _make_header({
                        'format': FORMAT_RAW,
                        'info': {
                            'type': 'bytes'
                        }
                    }))
                f.write(data)


class ObjectFile(BinaryFile):

    def load(self):
        with self.lock:
            with open(self.path, 'rb') as f:
                header = _get_header(f)
                if header.get('format', FORMAT_RAW) == FORMAT_XZ:
                    return dill.loads(
                        lzma.decompress(f.read(),
                                        format=lzma.FORMAT_RAW,
                                        filters=lzma_filters))
                else:
                    return dill.load(f)

    def dump(self, obj):
        with self.lock:
            with open(self.path, 'wb') as f:
                f.write(
                    _make_header({
                        'format': FORMAT_RAW,
                        'info': {
                            'type': 'pickle'
                        }
                    }))
                dill.dump(obj, f)


class ObjectListFile(ObjectFile):

    def clear(self):
        with self.lock:
            self._decompress()
            with open(self.path, 'wb') as f:
                f.write(
                    _make_header({
                        'format': FORMAT_RAW,
                        'info': {
                            'type': 'pickle_list'
                        }
                    }))

    def append(self, obj):
        with self.lock:
            with open(self.path, 'ab') as f:
                if f.tell() == 0:
                    f.write(
                        _make_header({
                            'format': FORMAT_RAW,
                            'info': {
                                'type': 'pickle_list'
                            }
                        }))
                dill.dump(obj, f)

    def __iter__(self):
        with self.lock:
            with open(self.path, 'rb') as f:
                while True:
                    try:
                        header = _get_header(f)
                    except AssertionError:
                        break
                    if header.get('format', FORMAT_RAW) == FORMAT_XZ:
                        yield from self._compressed_iter(f)
                    else:
                        yield from self._iter(f)

    def _compressed_iter(self, f):
        with lzma.open(f, 'rb', format=lzma.FORMAT_RAW,
                       filters=lzma_filters) as f:
            yield from self._iter(f)

    def _iter(self, f):
        while True:
            try:
                yield dill.load(f)
            except EOFError:
                break

    def asarray(self):
        return np.array(list(self))


class ArrayFile(BaseFile):

    def clear(self):
        with self.lock:
            with open(self.path, 'wb') as f:
                f.write(b'')

    def extend(self, data: np.ndarray):
        with self.lock:
            self._decompress()
            with open(self.path, 'ab') as f:
                if f.tell() == 0:
                    f.write(
                        _make_header({
                            'format': FORMAT_RAW,
                            'info': {
                                'type': 'array',
                                'dtype': data.dtype
                            }
                        }))
                f.write(data.tobytes())

    def append(self, data, dtype=float):
        self.extend(np.asarray(data, dtype=dtype))

    def asarray(self):
        with self.lock:
            with open(self.path, 'rb') as f:
                header = _get_header(f)
                dtype = header['info']['dtype']
                if header.get('format', FORMAT_RAW) == FORMAT_XZ:
                    return np.frombuffer(
                        lzma.decompress(f.read(),
                                        format=lzma.FORMAT_RAW,
                                        filters=lzma_filters),
                        dtype=dtype)
                else:
                    return np.fromfile(f, dtype=dtype)


def load(path):
    with open(path, 'rb') as f:
        header = _get_header(f)
        if header['info']['type'] == 'array':
            return ArrayFile(path)
        elif header['info']['type'] == 'pickle':
            return ObjectFile(path)
        elif header['info']['type'] == 'pickle_list':
            return ObjectListFile(path)
        elif header['info']['type'] == 'bytes':
            return BinaryFile(path)
        else:
            raise ValueError(f'Unknown file type: {header["info"]["type"]}')
