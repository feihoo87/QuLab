"""Dataset class - unified dataset storage for scan data.

This module provides the new unified Dataset class. The old Dataset class
remains in dataset.py for backward compatibility.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .array import Array
    from .local import DatasetRef, LocalStorage


class Dataset:
    """Dataset - unified storage for scan/experiment data.

    This class unifies the previous Record concept from scan.record
    with a more general dataset storage system.
    """

    def __init__(
        self,
        id: Optional[int],
        storage: "LocalStorage",
        name: str = "",
    ):
        self.id = id
        self.storage = storage
        self.name = name
        self._description: Optional[dict] = None
        self._arrays: dict[str, "Array"] = {}
        # Config and script caches (lazy loaded)
        self._config: Optional[dict] = None
        self._config_hash: Optional[str] = None
        self._script: Optional[str] = None
        self._script_hash: Optional[str] = None
        # Timestamp caches
        self._ctime: Optional[datetime] = None
        self._mtime: Optional[datetime] = None
        self._atime: Optional[datetime] = None

    def __repr__(self) -> str:
        return f"Dataset(id={self.id}, name={self.name!r}, arrays={self.keys()})"

    @classmethod
    def create(
        cls,
        storage: "LocalStorage",
        name: str,
        description: dict,
        config: Optional[dict] = None,
        script: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> "DatasetRef":
        """Create a new dataset in storage.

        Args:
            storage: LocalStorage instance
            name: Dataset name
            description: Dataset description dictionary
            config: Optional configuration dictionary
            script: Optional script code string
            tags: Optional list of tags

        Returns:
            DatasetRef for the created dataset
        """
        from .local import DatasetRef
        from .models import Dataset as DatasetModel
        from .models import get_or_create_config, get_or_create_script, get_or_create_tag

        with storage._get_session() as session:
            ds = DatasetModel(name=name, description=description)

            # Handle config if provided
            if config is not None:
                config_model = get_or_create_config(session, config, storage.base_path)
                session.flush()  # Flush to get the config ID
                ds.config_id = config_model.id
                config_model.ref_count += 1

            # Handle script if provided
            if script is not None:
                script_model = get_or_create_script(session, script, storage.base_path)
                session.flush()  # Flush to get the script ID
                ds.script_id = script_model.id
                script_model.ref_count += 1

            session.add(ds)
            session.flush()  # Flush to get the dataset ID

            # Add tags
            if tags:
                for tag_name in tags:
                    tag = get_or_create_tag(session, tag_name)
                    ds.tags.append(tag)

            session.commit()
            return DatasetRef(ds.id, storage, name=name)

    @classmethod
    def load(cls, storage: "LocalStorage", id: int) -> "Dataset":
        """Load a dataset from storage.

        Args:
            storage: LocalStorage instance
            id: Dataset ID

        Returns:
            Dataset instance

        Raises:
            KeyError: If dataset not found
        """
        from datetime import datetime

        from .models import Dataset as DatasetModel

        with storage._get_session() as session:
            ds_model = session.get(DatasetModel, id)
            if ds_model is None:
                raise KeyError(f"Dataset {id} not found")

            # Update access time
            ds_model.atime = datetime.now()
            session.commit()

            ds = cls(ds_model.id, storage, ds_model.name)
            ds._description = ds_model.description

            # Store config/script hash references for lazy loading
            if ds_model.config:
                ds._config_hash = ds_model.config.config_hash
            if ds_model.script:
                ds._script_hash = ds_model.script.script_hash

            # Cache timestamps
            ds._ctime = ds_model.ctime
            ds._mtime = ds_model.mtime
            ds._atime = ds_model.atime

            return ds

    @property
    def description(self) -> dict:
        """Get dataset description."""
        if self._description is None:
            from datetime import datetime

            from .models import Dataset as DatasetModel

            with self.storage._get_session() as session:
                ds_model = session.get(DatasetModel, self.id)
                if ds_model:
                    self._description = ds_model.description
                    ds_model.atime = datetime.now()
                    session.commit()
        return self._description or {}

    @property
    def config(self) -> Optional[dict]:
        """Get dataset configuration (lazy loaded from content-addressed storage)."""
        if self._config is None and self._config_hash is not None:
            from .models import load_config

            self._config = load_config(self._config_hash, self.storage.base_path)
        return self._config

    @property
    def config_hash(self) -> Optional[str]:
        """Get config hash (SHA1 identifier)."""
        return self._config_hash

    @property
    def script(self) -> Optional[str]:
        """Get dataset script code (lazy loaded from content-addressed storage)."""
        if self._script is None and self._script_hash is not None:
            from .models import load_script

            self._script = load_script(self._script_hash, self.storage.base_path)
        return self._script

    @property
    def script_hash(self) -> Optional[str]:
        """Get script hash (SHA1 identifier)."""
        return self._script_hash

    @property
    def ctime(self) -> Optional[datetime]:
        """Get creation time."""
        if self._ctime is None:
            from .models import Dataset as DatasetModel
            with self.storage._get_session() as session:
                ds_model = session.get(DatasetModel, self.id)
                if ds_model:
                    self._ctime = ds_model.ctime
        return self._ctime

    @property
    def mtime(self) -> Optional[datetime]:
        """Get modification time."""
        if self._mtime is None:
            from .models import Dataset as DatasetModel
            with self.storage._get_session() as session:
                ds_model = session.get(DatasetModel, self.id)
                if ds_model:
                    self._mtime = ds_model.mtime
        return self._mtime

    @property
    def atime(self) -> Optional[datetime]:
        """Get access time."""
        if self._atime is None:
            from .models import Dataset as DatasetModel
            with self.storage._get_session() as session:
                ds_model = session.get(DatasetModel, self.id)
                if ds_model:
                    self._atime = ds_model.atime
        return self._atime

    def keys(self) -> list[str]:
        """Get all array keys in this dataset."""
        from .models import Array as ArrayModel

        with self.storage._get_session() as session:
            arrays = (
                session.query(ArrayModel).filter_by(dataset_id=self.id).all()
            )
            return [a.name for a in arrays]

    def get_array(self, key: str) -> "Array":
        """Get an array by key.

        Args:
            key: Array name

        Returns:
            Array instance

        Raises:
            KeyError: If array not found
        """
        if key not in self._arrays:
            from .array import Array
            from .models import Array as ArrayModel

            with self.storage._get_session() as session:
                arr_model = (
                    session.query(ArrayModel)
                    .filter_by(dataset_id=self.id, name=key)
                    .first()
                )
                if arr_model is None:
                    raise KeyError(
                        f"Array {key} not found in dataset {self.id}"
                    )

                self._arrays[key] = Array.load(
                    self.storage,
                    self.id,
                    key,
                    arr_model.file_path,
                    arr_model.lu or (),
                    arr_model.rd or (),
                    arr_model.inner_shape or (),
                )

        return self._arrays[key]

    def create_array(
        self, key: str, inner_shape: tuple = ()
    ) -> "Array":
        """Create a new array in this dataset.

        Args:
            key: Array name
            inner_shape: Inner shape for nested arrays

        Returns:
            Array instance
        """
        from .array import Array
        from .models import Array as ArrayModel

        # Check if array already exists
        with self.storage._get_session() as session:
            existing = (
                session.query(ArrayModel)
                .filter_by(dataset_id=self.id, name=key)
                .first()
            )
            if existing:
                raise ValueError(
                    f"Array {key} already exists in dataset {self.id}"
                )

        # Create the array
        arr = Array.create(self.storage, self.id, key, inner_shape)

        # Save to database
        with self.storage._get_session() as session:
            arr_model = ArrayModel(
                dataset_id=self.id,
                name=key,
                file_path=str(arr.file.relative_to(self.storage.datasets_path / str(self.id))),
                inner_shape=list(inner_shape),
                lu=[],
                rd=[],
            )
            session.add(arr_model)
            session.commit()

        self._arrays[key] = arr
        return arr

    def append(self, position: tuple, data: dict[str, Any]):
        """Append data at a position.

        This is compatible with the original Record.append method.

        Args:
            position: Position tuple (level, step, pos, ...) or similar
            data: Dictionary of key -> value pairs
        """
        for key, value in data.items():
            if key not in self._arrays:
                # Auto-create array if needed
                import numpy as np

                inner_shape = np.asarray(value).shape if hasattr(value, "shape") else ()
                try:
                    self._arrays[key] = self.create_array(key, inner_shape)
                except ValueError:
                    # Array already exists, load it
                    self._arrays[key] = self.get_array(key)

            arr = self._arrays[key]
            arr.append(position, value)

            # Update database bounds
            from .models import Array as ArrayModel

            with self.storage._get_session() as session:
                arr_model = (
                    session.query(ArrayModel)
                    .filter_by(dataset_id=self.id, name=key)
                    .first()
                )
                if arr_model:
                    arr_model.lu = list(arr.lu)
                    arr_model.rd = list(arr.rd)
                    session.commit()

    def flush(self):
        """Flush all arrays to disk."""
        for arr in self._arrays.values():
            arr.flush()

    def delete(self):
        """Delete this dataset and all its arrays."""
        from .models import Dataset as DatasetModel
        from .models.config import decrement_config_ref
        from .models.script import decrement_script_ref

        # Delete array files
        for key in self.keys():
            try:
                arr = self.get_array(key)
                arr.delete()
            except KeyError:
                pass

        # Delete from database
        with self.storage._get_session() as session:
            ds = session.get(DatasetModel, self.id)
            if ds:
                # Decrement config ref count
                if ds.config_id:
                    decrement_config_ref(session, ds.config_id)
                # Decrement script ref count
                if ds.script_id:
                    decrement_script_ref(session, ds.script_id)
                session.delete(ds)
                session.commit()

    def get_documents(self) -> list["Document"]:
        """Get all documents derived from this dataset.

        Returns:
            List of Document objects
        """
        from .models import Dataset as DatasetModel

        with self.storage._get_session() as session:
            ds_model = session.get(DatasetModel, self.id)
            if ds_model is None:
                return []

            # Import here to avoid circular imports
            from .document import Document

            return [
                Document.load(self.storage, doc.id)
                for doc in ds_model.documents
            ]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "keys": self.keys(),
            "config_hash": self._config_hash,
            "script_hash": self._script_hash,
            "ctime": self.ctime.isoformat() if self.ctime else None,
            "mtime": self.mtime.isoformat() if self.mtime else None,
            "atime": self.atime.isoformat() if self.atime else None,
        }
