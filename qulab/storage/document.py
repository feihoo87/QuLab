"""Document class - unified document storage for workflow reports and general documents."""

import lzma
import pickle
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:
    from .local import LocalStorage


@dataclass
class Document:
    """Document - unified storage for workflow reports and general documents.

    This class replaces the previous Report concept from executor.storage
    with a more general document storage system.

    The `data` attribute is lazy-loaded from chunk storage on first access.
    """

    id: Optional[int] = None
    name: str = ""
    meta: dict = field(default_factory=dict)
    ctime: datetime = field(default_factory=datetime.now)
    mtime: datetime = field(default_factory=datetime.now)
    atime: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)

    # State fields (from Report's in_spec, bad_data, etc.)
    state: str = "unknown"  # 'ok', 'error', 'warning', 'unknown'
    version: int = 1
    parent_id: Optional[int] = None  # Version chain

    # Related datasets (not loaded by default)
    _dataset_ids: Optional[List[int]] = field(default=None, repr=False)

    # Script cache (lazy loaded)
    _script: Optional[str] = field(default=None, repr=False)
    _script_hash: Optional[str] = field(default=None, repr=False)

    # Data cache (lazy loaded from chunk storage)
    _data: Optional[dict] = field(default=None, repr=False)
    _chunk_hash: Optional[str] = field(default=None, repr=False)

    # Storage reference (needed for lazy loading)
    _storage: Optional["LocalStorage"] = field(default=None, repr=False)

    def __repr__(self) -> str:
        return f"Document(id={self.id}, name={self.name!r}, state={self.state})"

    @property
    def data(self) -> dict:
        """Get document data (lazy loaded from chunk storage)."""
        if self._data is None and self._chunk_hash is not None and self._storage is not None:
            from .chunk import load_chunk

            data_bytes = load_chunk(self._chunk_hash, base_path=self._storage.base_path)
            self._data = pickle.loads(lzma.decompress(data_bytes))
        return self._data if self._data is not None else {}

    @data.setter
    def data(self, value: dict):
        """Set document data."""
        self._data = value

    @property
    def dataset_ids(self) -> List[int]:
        """Get the IDs of datasets this document is derived from."""
        if self._dataset_ids is None:
            return []
        return self._dataset_ids

    @property
    def script(self) -> Optional[str]:
        """Get document script code (lazy loaded from content-addressed storage)."""
        if self._script is None and self._script_hash is not None:
            from .models import load_script

            self._script = load_script(self._script_hash, self._storage.base_path)
        return self._script

    @property
    def script_hash(self) -> Optional[str]:
        """Get script hash (SHA1 identifier)."""
        return self._script_hash

    def get_datasets(self, storage: "LocalStorage") -> List["Dataset"]:
        """Load and return the related datasets.

        Args:
            storage: LocalStorage instance

        Returns:
            List of Dataset objects
        """
        if self._dataset_ids is None:
            return []
        return [storage.get_dataset(ds_id) for ds_id in self._dataset_ids]

    @classmethod
    def create(
        cls,
        storage: "LocalStorage",
        name: str,
        data: dict,
        state: str = "unknown",
        tags: Optional[List[str]] = None,
        parent_id: Optional[int] = None,
        datasets: Optional[List[int]] = None,
        script: Optional[str] = None,
        **extra_meta,
    ) -> "DocumentRef":
        """Create a new document in storage.

        Args:
            storage: LocalStorage instance
            name: Document name
            data: Document data dictionary
            state: Document state
            tags: List of tags
            parent_id: Parent document ID for versioning
            datasets: List of dataset IDs this document is derived from
            script: Optional script code string
            **extra_meta: Additional metadata

        Returns:
            DocumentRef for the created document
        """
        from .chunk import save_chunk
        from .local import DocumentRef
        from .models import Dataset as DatasetModel
        from .models import Document as DocumentModel
        from .models import get_or_create_script, get_or_create_tag

        # Serialize and compress data
        data_bytes = lzma.compress(pickle.dumps(data))
        chunk_path, size = save_chunk(data_bytes, base_path=storage.base_path)

        # Get hash from path - chunk_path is like Path('chunks/xx/yy/zzzz')
        # We want just the filename (hash) part
        chunk_hash = chunk_path.name

        with storage._get_session() as session:
            # Determine version - if parent_id provided, increment parent's version
            version = 1
            if parent_id is not None:
                parent = session.get(DocumentModel, parent_id)
                if parent:
                    version = parent.version + 1

            # Create document model
            doc = DocumentModel(
                name=name,
                state=state,
                chunk_hash=chunk_hash,
                chunk_size=size,
                meta=extra_meta,
                parent_id=parent_id,
                version=version,
            )

            # Handle script if provided
            if script is not None:
                script_model = get_or_create_script(session, script, storage.base_path)
                session.flush()  # Flush to get the script ID
                doc.script_id = script_model.id
                script_model.ref_count += 1

            session.add(doc)

            # Add tags
            if tags:
                for tag_name in tags:
                    tag = get_or_create_tag(session, tag_name)
                    doc.tags.append(tag)

            # Add related datasets
            if datasets:
                for ds_id in datasets:
                    ds = session.get(DatasetModel, ds_id)
                    if ds:
                        doc.datasets.append(ds)

            session.commit()

            return DocumentRef(doc.id, storage, name=name)

    @classmethod
    def load(cls, storage: "LocalStorage", id: int) -> "Document":
        """Load a document from storage.

        Args:
            storage: LocalStorage instance
            id: Document ID

        Returns:
            Document instance

        Raises:
            KeyError: If document not found
        """
        from .models import Document as DocumentModel

        with storage._get_session() as session:
            doc_model = session.get(DocumentModel, id)
            if doc_model is None:
                raise KeyError(f"Document {id} not found")

            # Update access time
            doc_model.atime = datetime.now()
            session.commit()

            # Get script hash if available
            script_hash = doc_model.script.script_hash if doc_model.script else None

            return cls(
                id=doc_model.id,
                name=doc_model.name,
                meta=doc_model.meta,
                ctime=doc_model.ctime,
                mtime=doc_model.mtime,
                atime=doc_model.atime,
                tags=[t.name for t in doc_model.tags],
                state=doc_model.state,
                version=doc_model.version,
                parent_id=doc_model.parent_id,
                _dataset_ids=[ds.id for ds in doc_model.datasets],
                _script_hash=script_hash,
                _chunk_hash=doc_model.chunk_hash,
                _storage=storage,
            )

    def save(self, storage: "LocalStorage") -> "DocumentRef":
        """Save this document as a new version.

        Returns:
            DocumentRef for the new version
        """
        return self.create(
            storage,
            self.name,
            self.data,
            state=self.state,
            tags=self.tags,
            parent_id=self.id,
            datasets=self.dataset_ids,
            script=self.script,
            **self.meta,
        )

    def add_tag(self, tag: str) -> None:
        """Add a tag to this document.

        Args:
            tag: Tag name to add
        """
        if self._storage is None:
            raise RuntimeError("Document is not associated with a storage")

        from .models import Document as DocumentModel
        from .models import get_or_create_tag

        with self._storage._get_session() as session:
            doc_model = session.get(DocumentModel, self.id)
            if doc_model is None:
                raise KeyError(f"Document {self.id} not found")

            tag_model = get_or_create_tag(session, tag)
            doc_model.add_tag(tag_model)
            session.commit()

            # Update local cache
            if tag not in self.tags:
                self.tags.append(tag)

    def remove_tag(self, tag: str) -> None:
        """Remove a tag from this document.

        Args:
            tag: Tag name to remove
        """
        if self._storage is None:
            raise RuntimeError("Document is not associated with a storage")

        from .models import Document as DocumentModel
        from .models import Tag

        with self._storage._get_session() as session:
            doc_model = session.get(DocumentModel, self.id)
            if doc_model is None:
                raise KeyError(f"Document {self.id} not found")

            # Find and remove the tag
            tag_model = session.query(Tag).filter_by(name=tag).first()
            if tag_model:
                doc_model.remove_tag(tag_model)
                session.commit()

            # Update local cache
            if tag in self.tags:
                self.tags.remove(tag)

    def set_tags(self, tags: List[str]) -> None:
        """Set tags for this document (replace all existing tags).

        Args:
            tags: List of tag names
        """
        if self._storage is None:
            raise RuntimeError("Document is not associated with a storage")

        from .models import Document as DocumentModel
        from .models import get_or_create_tag

        with self._storage._get_session() as session:
            doc_model = session.get(DocumentModel, self.id)
            if doc_model is None:
                raise KeyError(f"Document {self.id} not found")

            # Clear existing tags
            doc_model.tags.clear()

            # Add new tags
            for tag_name in tags:
                tag_model = get_or_create_tag(session, tag_name)
                doc_model.tags.append(tag_model)

            session.commit()

            # Update local cache
            self.tags = list(tags)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "data": self.data,
            "meta": self.meta,
            "ctime": self.ctime.isoformat(),
            "mtime": self.mtime.isoformat(),
            "atime": self.atime.isoformat(),
            "tags": self.tags,
            "state": self.state,
            "version": self.version,
            "parent_id": self.parent_id,
            "script_hash": self._script_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Document":
        """Create from dictionary representation."""
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            meta=data.get("meta", {}),
            ctime=datetime.fromisoformat(data["ctime"]),
            mtime=datetime.fromisoformat(data["mtime"]),
            atime=datetime.fromisoformat(data["atime"]),
            tags=data.get("tags", []),
            state=data.get("state", "unknown"),
            version=data.get("version", 1),
            parent_id=data.get("parent_id"),
            _data=data.get("data", {}),
            _script_hash=data.get("script_hash") or data.get("_script_hash"),
            _dataset_ids=data.get("dataset_ids") or data.get("_dataset_ids"),
            _script=data.get("script") or data.get("_script"),
        )
