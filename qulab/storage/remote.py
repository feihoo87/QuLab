"""RemoteStorage implementation - ZMQ client for remote storage access."""

from typing import TYPE_CHECKING, Any, Iterator, List, Optional

import zmq

from .base import Storage

if TYPE_CHECKING:
    from datetime import datetime

    from .datastore import Dataset
    from .document import Document


class RemoteStorage(Storage):
    """Remote storage client (ZMQ).

    Connects to a StorageServer over ZMQ to access remote storage.
    """

    def __init__(
        self,
        server_address: str = "tcp://127.0.0.1:6789",
        timeout: float = 30.0,
    ):
        """Initialize remote storage client.

        Args:
            server_address: ZMQ address of the storage server
            timeout: Request timeout in seconds
        """
        self.server_address = server_address
        self.timeout = timeout
        self._socket = None  # For connection reuse

    @property
    def is_remote(self) -> bool:
        return True

    def _call(self, method: str, **kwargs) -> Any:
        """Call a remote method.

        Args:
            method: Method name to call
            **kwargs: Method arguments

        Returns:
            Response from the server
        """
        from qulab.sys.rpc.zmq_socket import ZMQContextManager

        with ZMQContextManager(
            zmq.DEALER,
            connect=self.server_address,
            socket=self._socket,
            timeout=self.timeout,
        ) as sock:
            sock.send_pyobj({"method": method, **kwargs})
            return sock.recv_pyobj()

    # Document API
    def create_document(
        self,
        name: str,
        data: dict,
        state: str = "unknown",
        tags: Optional[List[str]] = None,
        script: Optional[str] = None,
        **meta,
    ) -> "RemoteDocumentRef":
        """Create a new document on the remote server."""
        doc_id = self._call(
            "document_create",
            name=name,
            data=data,
            state=state,
            tags=tags,
            script=script,
            meta=meta,
        )
        return RemoteDocumentRef(doc_id, self, name=name)

    def get_document(self, id: int) -> "RemoteDocument":
        """Get a document from the remote server."""
        return RemoteDocument(id, self)

    def query_documents(
        self,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        state: Optional[str] = None,
        before: Optional["datetime"] = None,
        after: Optional["datetime"] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Iterator["RemoteDocumentRef"]:
        """Query documents on the remote server."""
        result = self._call(
            "document_query",
            name=name,
            tags=tags,
            state=state,
            before=before,
            after=after,
            offset=offset,
            limit=limit,
        )
        total, results = result
        for r in results:
            yield RemoteDocumentRef(r["id"], self, name=r.get("name", ""))

    def count_documents(
        self,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        state: Optional[str] = None,
        before: Optional["datetime"] = None,
        after: Optional["datetime"] = None,
    ) -> int:
        """Count documents on the remote server."""
        return self._call(
            "document_count",
            name=name,
            tags=tags,
            state=state,
            before=before,
            after=after,
        )

    # Dataset API
    def create_dataset(
        self,
        name: str,
        description: dict,
        config: Optional[dict] = None,
        script: Optional[str] = None,
    ) -> "RemoteDatasetRef":
        """Create a new dataset on the remote server."""
        ds_id = self._call(
            "dataset_create",
            name=name,
            description=description,
            config=config,
            script=script,
        )
        return RemoteDatasetRef(ds_id, self, name=name)

    def get_dataset(self, id: int) -> "RemoteDataset":
        """Get a dataset from the remote server."""
        return RemoteDataset(id, self)

    def query_datasets(
        self,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        before: Optional["datetime"] = None,
        after: Optional["datetime"] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Iterator["RemoteDatasetRef"]:
        """Query datasets on the remote server."""
        result = self._call(
            "dataset_query",
            name=name,
            tags=tags,
            before=before,
            after=after,
            offset=offset,
            limit=limit,
        )
        total, results = result
        for r in results:
            yield RemoteDatasetRef(r["id"], self, name=r.get("name", ""))

    def count_datasets(
        self,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        before: Optional["datetime"] = None,
        after: Optional["datetime"] = None,
    ) -> int:
        """Count datasets on the remote server."""
        return self._call(
            "dataset_count",
            name=name,
            tags=tags,
            before=before,
            after=after,
        )


class RemoteDocumentRef:
    """Reference to a remote document."""

    def __init__(self, id: int, storage: RemoteStorage, name: str = ""):
        self.id = id
        self.storage = storage
        self.name = name

    def get(self) -> dict:
        """Load the document data."""
        return self.storage._call("document_get", id=self.id)

    def delete(self) -> bool:
        """Delete the document."""
        return self.storage._call("document_delete", id=self.id)

    def __repr__(self) -> str:
        return f"RemoteDocumentRef(id={self.id}, name={self.name!r})"


class RemoteDocument:
    """Proxy for a remote document."""

    def __init__(self, id: int, storage: RemoteStorage):
        self.id = id
        self.storage = storage

    def get_data(self) -> dict:
        """Get document data."""
        return self.storage._call("document_get_data", id=self.id)

    def __repr__(self) -> str:
        return f"RemoteDocument(id={self.id})"


class RemoteDatasetRef:
    """Reference to a remote dataset."""

    def __init__(self, id: int, storage: RemoteStorage, name: str = ""):
        self.id = id
        self.storage = storage
        self.name = name

    def get(self) -> "RemoteDataset":
        """Load the dataset proxy."""
        return RemoteDataset(self.id, self.storage)

    def delete(self) -> bool:
        """Delete the dataset."""
        return self.storage._call("dataset_delete", id=self.id)

    def __repr__(self) -> str:
        return f"RemoteDatasetRef(id={self.id}, name={self.name!r})"


class RemoteDataset:
    """Proxy for a remote dataset."""

    def __init__(self, id: int, storage: RemoteStorage):
        self.id = id
        self.storage = storage

    def get_info(self) -> dict:
        """Get dataset information."""
        return self.storage._call("dataset_get", id=self.id)

    def keys(self) -> list[str]:
        """Get array keys."""
        info = self.get_info()
        return info.get("keys", [])

    def append(self, position: tuple, data: dict[str, Any]) -> bool:
        """Append data to the dataset."""
        return self.storage._call(
            "dataset_append", id=self.id, position=position, data=data
        )

    def get_array(self, key: str) -> "RemoteArray":
        """Get a remote array proxy."""
        return RemoteArray(self.id, key, self.storage)

    def __repr__(self) -> str:
        return f"RemoteDataset(id={self.id})"


class RemoteArray:
    """Proxy for a remote array."""

    def __init__(self, dataset_id: int, key: str, storage: RemoteStorage):
        self.dataset_id = dataset_id
        self.key = key
        self.storage = storage

    def getitem(self, index: tuple) -> Any:
        """Get an item by index."""
        return self.storage._call(
            "array_getitem",
            dataset_id=self.dataset_id,
            key=self.key,
            index=index,
        )

    def iter(self, start: int = 0, count: int = 100) -> list:
        """Iterate over array items."""
        return self.storage._call(
            "array_iter",
            dataset_id=self.dataset_id,
            key=self.key,
            start=start,
            count=count,
        )

    def toarray(self) -> Any:
        """Convert to numpy array."""
        import numpy as np

        items = []
        start = 0
        while True:
            batch = self.iter(start=start, count=1000)
            if not batch:
                break
            items.extend([v for _, v in batch])
            start += len(batch)
            if len(batch) < 1000:
                break
        return np.array(items)

    def __repr__(self) -> str:
        return f"RemoteArray(dataset_id={self.dataset_id}, key={self.key!r})"
