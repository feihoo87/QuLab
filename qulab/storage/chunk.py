import hashlib
import zlib
from pathlib import Path

DATAPATH = Path.home() / 'data'
CHUNKSIZE = 1024 * 1024 * 4  # 4 MB


def set_data_path(base_path: str) -> None:
    global DATAPATH
    DATAPATH = Path(base_path)


def get_data_path() -> Path:
    return DATAPATH


def save_chunk(data: bytes, compressed: bool = False) -> tuple[str, str]:
    if compressed:
        data = zlib.compress(data)
    hashstr = hashlib.sha1(data).hexdigest()
    file = get_data_path(
    ) / 'chunks' / hashstr[:2] / hashstr[2:4] / hashstr[4:]
    file.parent.mkdir(parents=True, exist_ok=True)
    with open(file, 'wb') as f:
        f.write(data)
    return str('/'.join(file.parts[-4:])), len(data)


def load_chunk(file: str, compressed: bool = False) -> bytes:
    if file.startswith('chunks/'):
        with open(get_data_path() / file, 'rb') as f:
            data = f.read()
    elif file.startswith('packs/'):
        *filepath, start, size = file.split('/')
        filepath = '/'.join(filepath)
        with open(get_data_path() / filepath, 'rb') as f:
            f.seek(int(start))
            data = f.read(int(size))
    else:
        raise ValueError('Invalid file path: ' + file)
    if compressed:
        data = zlib.decompress(data)
    return data


def pack_chunk(pack: str, chunkfile: str) -> str:
    pack = get_data_path() / 'packs' / pack
    pack.parent.mkdir(parents=True, exist_ok=True)
    with open(pack, 'ab') as f:
        buf = load_chunk(chunkfile)
        start = f.tell()
        size = len(buf)
        f.write(buf)
    return str('/'.join(pack.parts[-2:])) + '/' + str(start) + '/' + str(size)


def delete_chunk(file: str):
    file = get_data_path() / file
    file.unlink()
