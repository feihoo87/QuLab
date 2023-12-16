import shutil
from abc import ABC, abstractmethod
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid1, uuid5

from .file import load


class BaseStorage(ABC):

    @abstractmethod
    def _create_dataset(self) -> UUID:
        """Create a new dataset and return its id"""
        pass

    @abstractmethod
    def _delet_dataset(self, id: UUID):
        """Delete a dataset"""
        pass

    @abstractmethod
    def _dataset_getitem(self, id: UUID, key: str):
        """Get a dataset item"""
        pass

    @abstractmethod
    def _dataset_setitem(self, id: UUID, key: str, value: Any):
        """Set a dataset item"""
        pass

    @abstractmethod
    def _dataset_delitem(self, id: UUID, key: str):
        """Delete a dataset item"""
        pass

    @abstractmethod
    def _dataset_keys(self, id: UUID):
        """Get dataset keys"""
        pass

    @abstractmethod
    def _dataset_append(self, id: UUID, dataframe: dict[str, Any]):
        """Append a dataframe to a dataset"""
        pass

    @abstractmethod
    def _dataset_item_append(self, id: UUID, key: str, value: Any):
        """Append a value to a dataset item"""
        pass


class Storage(BaseStorage):

    def __init__(self, base: Path | str):
        if isinstance(base, str):
            base = Path(base)
        self.base = base
        self.namespace = uuid5(UUID('f89f735a-791e-5a43-9ba6-f28d58601544'),
                               base.as_posix())

    def clear(self):
        shutil.rmtree(self.base)
        self.base.mkdir(parents=True)

    def uuid(self,
             name: str | None = None,
             namespace: UUID | None = None,
             seq: int = 0) -> UUID:
        if name is None:
            name = str(uuid1())
        if namespace is None:
            return uuid5(self.namespace, f"{name}{seq}")
        else:
            return uuid5(namespace, f"{name}{seq}")

    def uuid_to_path(self, uuid: UUID) -> Path:
        return self.base / uuid.hex[:2] / uuid.hex[2:4] / uuid.hex[4:]

    def create_dataset(self, title: str, tags: list[str] = []):
        from .dataset import Dataset
        id = self.uuid()
        return Dataset(id, self)

    def get_dataset(self, id: UUID):
        from .dataset import Dataset
        return Dataset(id, self)

    def remove_dataset(self, id: UUID):
        shutil.rmtree(self.uuid_to_path(id))

    def query(self, title_pattern: str, tags: list[str],
              before: datetime | date, after: datetime | date):
        pass
