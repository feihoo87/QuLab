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


def save_chunk(data: bytes, compressed: bool = False, base_path: Path | None = None) -> tuple[Path, int]:
    """Save a chunk of data using content-addressed storage.

    Args:
        data: Raw bytes to store
        compressed: Whether to compress the data with zlib
        base_path: Optional base path (defaults to DATAPATH)

    Returns:
        Tuple of (relative_path, size_in_bytes)
    """
    if compressed:
        data = zlib.compress(data)
    hashstr = hashlib.sha1(data).hexdigest()

    base = base_path if base_path is not None else get_data_path()
    # Use full hash for filename to ensure we can reconstruct the path correctly
    file = base / 'chunks' / hashstr[:2] / hashstr[2:4] / hashstr
    file.parent.mkdir(parents=True, exist_ok=True)
    with open(file, 'wb') as f:
        f.write(data)
    # Always return the relative path from base
    return file.relative_to(base), len(data)


def load_chunk(file: str | Path, compressed: bool = False, base_path: Path | None = None) -> bytes:
    """Load a chunk of data from content-addressed storage.

    Args:
        file: Path to the chunk (relative or absolute)
        compressed: Whether the data is zlib compressed
        base_path: Optional base path (defaults to DATAPATH)

    Returns:
        Raw bytes
    """
    base = base_path if base_path is not None else get_data_path()

    if isinstance(file, Path):
        filepath = base / file
    elif isinstance(file, str):
        # Normalize path separators for cross-platform compatibility
        # Windows uses backslashes, but we need forward slashes for checks
        normalized = file.replace('\\', '/')
        if normalized.startswith('chunks/'):
            filepath = base / file
        elif normalized.startswith('packs/'):
            *filepath_parts, start, size = normalized.split('/')
            filepath = base / '/'.join(filepath_parts)
            with open(filepath, 'rb') as f:
                f.seek(int(start))
                data = f.read(int(size))
                if compressed:
                    data = zlib.decompress(data)
                return data
        else:
            # Assume it's a relative path or hash
            # Use full hash for filename to match save_chunk behavior
            filepath = base / 'chunks' / file[:2] / file[2:4] / file
    else:
        raise ValueError('Invalid file path: ' + str(file))

    with open(filepath, 'rb') as f:
        data = f.read()
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
