"""Array class - multidimensional array storage for scan data."""

import sys
import uuid
from pathlib import Path
from threading import Lock
from types import EllipsisType
from typing import TYPE_CHECKING, Any, Iterator, List, Optional, Tuple, Union

import dill
import numpy as np

if TYPE_CHECKING:
    from .local import LocalStorage


class Array:
    """Multidimensional array storage - based on BufferList from scan.record.

    Stores sparse multidimensional data with file backing. Supports
    numpy-style slicing and efficient appends.
    """

    BUFFER_SIZE = 1000  # Memory buffer size before flush

    def __init__(
        self,
        name: str,
        storage: "LocalStorage",
        dataset_id: int,
        file: Optional[Union[Path, str]] = None,
    ):
        self.name = name
        self.storage = storage
        self.dataset_id = dataset_id

        self._list: List[Tuple[Tuple, Any]] = []
        self._lock = Lock()
        self._slice: Optional[Tuple] = None

        # Bounds
        self.lu: tuple = ()
        self.rd: tuple = ()
        self.inner_shape: tuple = ()

        self._file: Optional[Path] = None
        if file is not None:
            self.file = Path(file) if isinstance(file, str) else file

    def __repr__(self) -> str:
        return f"Array(name={self.name!r}, shape={self.shape}, lu={self.lu}, rd={self.rd})"

    def __getstate__(self) -> dict:
        """Serialize for pickle."""
        self.flush()
        return {
            "file": str(self.file) if self.file else None,
            "lu": self.lu,
            "rd": self.rd,
            "inner_shape": self.inner_shape,
        }

    def __setstate__(self, state: dict):
        """Deserialize from pickle."""
        file_path = state.get("file")
        self.file = Path(file_path) if file_path else None
        self.lu = state["lu"]
        self.rd = state["rd"]
        self.inner_shape = state["inner_shape"]
        self._list = []
        self._slice = None
        self._lock = Lock()
        self.storage = None  # Will be set by parent Dataset
        self.dataset_id = None
        self.name = None

    @property
    def file(self) -> Optional[Path]:
        return self._file

    @file.setter
    def file(self, path: Optional[Path]):
        self._file = path

    @property
    def shape(self) -> tuple:
        """Logical shape of the array."""
        if not self.lu or not self.rd:
            return ()
        outer = tuple(r - l for l, r in zip(self.lu, self.rd))
        return outer + self.inner_shape

    @classmethod
    def create(
        cls,
        storage: "LocalStorage",
        dataset_id: int,
        name: str,
        inner_shape: tuple = (),
    ) -> "Array":
        """Create a new array in storage.

        Args:
            storage: LocalStorage instance
            dataset_id: Parent dataset ID
            name: Array name
            inner_shape: Inner shape for nested arrays

        Returns:
            New Array instance
        """
        # Generate storage path using UUID sharding
        s = uuid.uuid4().hex
        path = Path(s[:2]) / s[2:4] / s[4:6] / s[6:]
        full_path = storage.datasets_path / str(dataset_id) / path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        instance = cls(name, storage, dataset_id, file=full_path)
        instance.inner_shape = inner_shape
        instance.lu = tuple([0] * len(inner_shape)) if inner_shape else ()
        instance.rd = tuple([1] * len(inner_shape)) if inner_shape else ()

        return instance

    @classmethod
    def load(
        cls,
        storage: "LocalStorage",
        dataset_id: int,
        name: str,
        file_path: Union[str, Path],
        lu: tuple,
        rd: tuple,
        inner_shape: tuple,
    ) -> "Array":
        """Load an existing array from storage.

        Args:
            storage: LocalStorage instance
            dataset_id: Parent dataset ID
            name: Array name
            file_path: Path to the data file
            lu: Lower bounds
            rd: Upper bounds
            inner_shape: Inner shape

        Returns:
            Array instance
        """
        instance = cls(name, storage, dataset_id)
        instance._file = storage.datasets_path / str(dataset_id) / file_path
        instance.lu = tuple(lu) if lu else ()
        instance.rd = tuple(rd) if rd else ()
        instance.inner_shape = tuple(inner_shape) if inner_shape else ()
        return instance

    def flush(self):
        """Flush memory buffer to disk."""
        if not self._list:
            return

        with self._lock:
            buffer, self._list = self._list, []

        if self._file:
            with self._lock:
                with open(self._file, "ab") as f:
                    for item in buffer:
                        dill.dump(item, f)

    def delete(self):
        """Delete the array file."""
        self.flush()
        if self._file and self._file.exists():
            self._file.unlink()
            self._file = None

    def append(self, pos: Tuple, value: Any, dims: Optional[Tuple] = None):
        """Append a value at a position.

        Args:
            pos: Position tuple
            value: Value to store
            dims: Optional dimension filtering (only store if pos matches in dims)
        """
        if dims is not None:
            if any(p != 0 for i, p in enumerate(pos) if i not in dims):
                return
            pos = tuple(pos[i] for i in dims)

        # Update bounds
        if not self.lu:
            self.lu = pos
            self.rd = tuple(p + 1 for p in pos)
        else:
            self.lu = tuple(min(i, j) for i, j in zip(pos, self.lu))
            self.rd = tuple(max(i + 1, j) for i, j in zip(pos, self.rd))

        # Track inner shape
        if hasattr(value, "shape"):
            if not self.inner_shape:
                self.inner_shape = value.shape
            elif self.inner_shape != value.shape:
                self.inner_shape = ()

        with self._lock:
            self._list.append((pos, value))

        if len(self._list) >= self.BUFFER_SIZE:
            self.flush()

    def _iter_file(self) -> Iterator[Tuple[Tuple, Any]]:
        """Iterate over file-stored items."""
        if self._file and self._file.exists():
            with self._lock:
                with open(self._file, "rb") as f:
                    while True:
                        try:
                            pos, value = dill.load(f)
                            yield pos, value
                        except EOFError:
                            break

    def iter(self) -> Iterator[Tuple[Tuple, Any]]:
        """Iterate over all items (file + memory buffer)."""
        self.flush()

        for pos, value in self._iter_file():
            if self._slice:
                # Apply slice filtering
                if all(self._index_in_slice(s, i) for s, i in zip(self._slice, pos)):
                    if self.inner_shape:
                        # Convert to numpy array for multi-dimensional slicing
                        arr = np.asarray(value)
                        yield pos, arr[self._slice[len(pos) :]]
                    else:
                        yield pos, value
            else:
                yield pos, value

        # Also yield from memory buffer
        for pos, value in self._list:
            if self._slice:
                if all(self._index_in_slice(s, i) for s, i in zip(self._slice, pos)):
                    if self.inner_shape:
                        # Convert to numpy array for multi-dimensional slicing
                        arr = np.asarray(value)
                        yield pos, arr[self._slice[len(pos) :]]
                    else:
                        yield pos, value
            else:
                yield pos, value

    def value(self) -> List:
        """Return all values as a list."""
        return [v for _, v in self.iter()]

    def positions(self) -> List:
        """Return all positions as a list."""
        return [p for p, _ in self.iter()]

    def items(self) -> Tuple[List, List]:
        """Return (positions, values) as separate lists."""
        p, d = [], []
        for pos, value in self.iter():
            p.append(pos)
            d.append(value)
        return p, d

    def toarray(self) -> np.ndarray:
        """Convert to numpy array (dense representation)."""
        pos, data = self.items()

        # Always return full array, ignore self._slice
        shape = tuple(r - l for l, r in zip(self.lu, self.rd))
        pos = np.asarray(pos) - np.asarray(self.lu)

        data = np.asarray(data)
        if data.size == 0:
            return np.array([])

        inner_shape = data.shape[1:]
        full_shape = shape + inner_shape

        # Create output array with NaN fill
        dtype = data.dtype if hasattr(data.dtype, "kind") else float
        x = np.full(full_shape, np.nan, dtype=dtype)

        # Fill in the data
        if pos.size > 0:
            x[tuple(pos.T)] = data
        return x

    def _index_in_slice(self, slice_obj: slice | int, index: int) -> bool:
        """Check if index is within a slice."""
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

    def _full_slice(
        self, slice_tuple: slice | int | EllipsisType | tuple
    ) -> tuple[tuple, list, list]:
        """Normalize slice to full dimensions."""
        ndim = len(self.lu)
        if self.inner_shape:
            ndim += len(self.inner_shape)

        if isinstance(slice_tuple, slice):
            slice_tuple = (slice_tuple,) + (slice(0, sys.maxsize, 1),) * (ndim - 1)
        elif slice_tuple is ...:
            slice_tuple = (slice(0, sys.maxsize, 1),) * ndim
        else:
            head, tail = (), ()
            for i, s in enumerate(slice_tuple):
                if s is ...:
                    head = slice_tuple[:i]
                    tail = slice_tuple[i + 1 :]
                    break
            else:
                head = slice_tuple
            slice_tuple = head + (slice(0, sys.maxsize, 1),) * (
                ndim - len(head) - len(tail)
            ) + tail

        slice_list = []
        contract = []
        reversed_dims = []

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
                    reversed_dims.append(i)
                    if start is None and stop is None:
                        start, stop = 0, sys.maxsize
                    elif start is None:
                        start, stop = self.lu[i], sys.maxsize
                    elif stop is None:
                        start, stop = 0, start + self.lu[i]
                    else:
                        start, stop = stop + self.lu[i] + 1, start + self.lu[i] + 1

                if start is None:
                    start = 0
                elif start < 0 and i < len(self.lu):
                    start = self.rd[i] + start
                if stop is None:
                    stop = sys.maxsize
                elif stop < 0 and i < len(self.lu):
                    stop = self.rd[i] + stop

                slice_list.append(slice(start, stop, step))

        return tuple(slice_list), contract, reversed_dims

    def __getitem__(self, slice_tuple):
        """Support numpy-style indexing."""
        # Convert single index to tuple
        if not isinstance(slice_tuple, tuple):
            slice_tuple = (slice_tuple,)

        full_slice, contract, reversed_dims = self._full_slice(slice_tuple)

        # Get full array
        ret = self.toarray()

        if ret.size == 0:
            return ret

        ndim = len(ret.shape)

        # Build slice tuple for the result
        slices = []
        for i in range(ndim):
            s = full_slice[i] if i < len(full_slice) else slice(None)
            if i in contract:
                # Use integer index for contracted dimensions
                slices.append(s.start if isinstance(s, slice) else 0)
            elif isinstance(s, slice):
                # Normalize slice bounds relative to array bounds
                start = s.start if s.start is not None else 0
                stop = s.stop if s.stop is not None else ret.shape[i]
                # Clamp to valid range
                start = max(0, min(start, ret.shape[i]))
                stop = max(0, min(stop, ret.shape[i]))
                if i in reversed_dims:
                    # For reversed dims, swap start/stop and use negative step
                    # Use None instead of -1 for stop to include index 0
                    rev_start = stop - 1 if stop > 0 else None
                    rev_stop = start - 1 if start > 0 else None
                    slices.append(slice(rev_start, rev_stop, -1))
                else:
                    slices.append(slice(start, stop, s.step))
            else:
                slices.append(s)

        ret = ret.__getitem__(tuple(slices))
        return ret
