"""LocalStorage implementation - file-based storage with SQLite metadata."""

import lzma
import pickle
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, List, Optional, Union

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .base import Storage

if TYPE_CHECKING:
    from datetime import datetime


class LocalStorage(Storage):
    """Local file storage implementation.

    Stores metadata in SQLite and data in content-addressed chunks on disk.
    """

    def __init__(self, base_path: Union[str, Path], db_url: Optional[str] = None):
        """Initialize local storage.

        Args:
            base_path: Base directory for all storage files
            db_url: SQLAlchemy database URL (default: sqlite:///{base_path}/storage.db)
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Database connection
        if db_url is None:
            db_url = f"sqlite:///{self.base_path / 'storage.db'}"
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

        # Initialize tables
        from .models import Base

        Base.metadata.create_all(self.engine)

        # Subdirectories
        self.documents_path = self.base_path / "documents"
        self.datasets_path = self.base_path / "datasets"
        self.chunks_path = self.base_path / "chunks"

        for p in [self.documents_path, self.datasets_path, self.chunks_path]:
            p.mkdir(parents=True, exist_ok=True)

    @property
    def is_remote(self) -> bool:
        return False

    def _get_session(self):
        """Get a new database session."""
        return self.Session()

    # Document API
    def create_document(
        self,
        name: str,
        data: dict,
        state: str = "unknown",
        tags: Optional[List[str]] = None,
        script: Optional[str] = None,
        **meta,
    ) -> "DocumentRef":
        """Create a new document."""
        from .document import Document

        return Document.create(self, name, data, state=state, tags=tags, script=script, **meta)

    def get_document(self, id: int) -> "Document":
        """Get a document by ID."""
        from .document import Document

        return Document.load(self, id)

    def query_documents(
        self,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        state: Optional[str] = None,
        before: Optional["datetime"] = None,
        after: Optional["datetime"] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Iterator["DocumentRef"]:
        """Query documents with filters."""
        from .models import query_documents

        with self._get_session() as session:
            docs = query_documents(
                session,
                name=name,
                tags=tags,
                state=state,
                before=before,
                after=after,
                offset=offset,
                limit=limit,
            )
            for doc in docs:
                yield DocumentRef(doc.id, self, name=doc.name)

    def count_documents(
        self,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        state: Optional[str] = None,
        before: Optional["datetime"] = None,
        after: Optional["datetime"] = None,
    ) -> int:
        """Count documents matching filters."""
        from .models import count_documents

        with self._get_session() as session:
            return count_documents(
                session, name=name, tags=tags, state=state, before=before, after=after
            )

    def get_latest_document(
        self,
        name: str,
        state: Optional[str] = None,
    ) -> Optional["DocumentRef"]:
        """Get the latest document by name.

        This is the most common query pattern - finding the most
        recent document with a given name.

        Args:
            name: Document name (exact match)
            state: Optional state filter

        Returns:
            DocumentRef to the most recent document, or None if not found
        """
        from .models import get_latest_document

        with self._get_session() as session:
            doc = get_latest_document(session, name=name, state=state)
            if doc is None:
                return None
            return DocumentRef(doc.id, self, name=doc.name)

    # Dataset API
    def create_dataset(
        self,
        name: str,
        description: dict,
        config: Optional[dict] = None,
        script: Optional[str] = None,
    ) -> "DatasetRef":
        """Create a new dataset."""
        from .datastore import Dataset

        return Dataset.create(self, name, description, config=config, script=script)

    def get_dataset(self, id: int) -> "Dataset":
        """Get a dataset by ID."""
        from .datastore import Dataset

        return Dataset.load(self, id)

    def query_datasets(
        self,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        before: Optional["datetime"] = None,
        after: Optional["datetime"] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Iterator["DatasetRef"]:
        """Query datasets with filters."""
        from .models import query_datasets

        with self._get_session() as session:
            datasets = query_datasets(
                session,
                name=name,
                tags=tags,
                before=before,
                after=after,
                offset=offset,
                limit=limit,
            )
            for ds in datasets:
                yield DatasetRef(ds.id, self, name=ds.name)

    def count_datasets(
        self,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        before: Optional["datetime"] = None,
        after: Optional["datetime"] = None,
    ) -> int:
        """Count datasets matching filters."""
        from .models import count_datasets

        with self._get_session() as session:
            return count_datasets(
                session, name=name, tags=tags, before=before, after=after
            )


class DocumentRef:
    """Lightweight reference to a document in local storage."""

    def __init__(self, id: int, storage: LocalStorage, name: str = ""):
        self.id = id
        self.storage = storage
        self.name = name

    def get(self) -> "Document":
        """Load the full document."""
        from .document import Document

        return Document.load(self.storage, self.id)

    def delete(self) -> bool:
        """Delete the document."""
        from .models import Document as DocumentModel
        from .models.script import decrement_script_ref

        with self.storage._get_session() as session:
            doc = session.get(DocumentModel, self.id)
            if doc:
                # Decrement script ref count if applicable
                if doc.script_id:
                    decrement_script_ref(session, doc.script_id)
                session.delete(doc)
                session.commit()
                return True
            return False

    def __repr__(self) -> str:
        return f"DocumentRef(id={self.id}, name={self.name!r})"


class DatasetRef:
    """Lightweight reference to a dataset in local storage."""

    def __init__(self, id: int, storage: LocalStorage, name: str = ""):
        self.id = id
        self.storage = storage
        self.name = name

    def get(self) -> "Dataset":
        """Load the full dataset."""
        from .datastore import Dataset

        return Dataset.load(self.storage, self.id)

    def delete(self) -> bool:
        """Delete the dataset."""
        from .models import Dataset as DatasetModel

        with self.storage._get_session() as session:
            ds = session.get(DatasetModel, self.id)
            if ds:
                session.delete(ds)
                session.commit()
                return True
            return False

    def __repr__(self) -> str:
        return f"DatasetRef(id={self.id}, name={self.name!r})"
