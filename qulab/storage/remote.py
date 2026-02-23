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
        tags: Optional[List[str]] = None,
    ) -> "RemoteDatasetRef":
        """Create a new dataset on the remote server."""
        ds_id = self._call(
            "dataset_create",
            name=name,
            description=description,
            config=config,
            script=script,
            tags=tags,
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

    # Document tag editing API
    def document_add_tags(self, id: int, tags: List[str]) -> None:
        """Add tags to a document on the remote server.

        Args:
            id: Document ID
            tags: List of tag names to add
        """
        self._call("document_add_tags", id=id, tags=tags)

    def document_remove_tags(self, id: int, tags: List[str]) -> None:
        """Remove tags from a document on the remote server.

        Args:
            id: Document ID
            tags: List of tag names to remove
        """
        self._call("document_remove_tags", id=id, tags=tags)

    def document_set_tags(self, id: int, tags: List[str]) -> None:
        """Set tags for a document on the remote server (replace all).

        Args:
            id: Document ID
            tags: List of tag names
        """
        self._call("document_set_tags", id=id, tags=tags)

    # Dataset tag editing API
    def dataset_add_tags(self, id: int, tags: List[str]) -> None:
        """Add tags to a dataset on the remote server.

        Args:
            id: Dataset ID
            tags: List of tag names to add
        """
        self._call("dataset_add_tags", id=id, tags=tags)

    def dataset_remove_tags(self, id: int, tags: List[str]) -> None:
        """Remove tags from a dataset on the remote server.

        Args:
            id: Dataset ID
            tags: List of tag names to remove
        """
        self._call("dataset_remove_tags", id=id, tags=tags)

    def dataset_set_tags(self, id: int, tags: List[str]) -> None:
        """Set tags for a dataset on the remote server (replace all).

        Args:
            id: Dataset ID
            tags: List of tag names
        """
        self._call("dataset_set_tags", id=id, tags=tags)


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
        self._info: Optional[dict] = None

    def _get_info(self) -> dict:
        """Get document info (cached)."""
        if self._info is None:
            self._info = self.storage._call("document_get", id=self.id)
        return self._info

    def get_data(self) -> dict:
        """Get document data."""
        return self.storage._call("document_get_data", id=self.id)

    @property
    def tags(self) -> list[str]:
        """Get document tags."""
        return self._get_info().get("tags", [])

    def add_tag(self, tag: str) -> None:
        """Add a tag to this document."""
        self.storage.document_add_tags(self.id, [tag])
        if self._info is not None:
            if tag not in self._info.get("tags", []):
                self._info.setdefault("tags", []).append(tag)

    def remove_tag(self, tag: str) -> None:
        """Remove a tag from this document."""
        self.storage.document_remove_tags(self.id, [tag])
        if self._info is not None:
            if tag in self._info.get("tags", []):
                self._info["tags"].remove(tag)

    def set_tags(self, tags: list[str]) -> None:
        """Set tags for this document (replace all)."""
        self.storage.document_set_tags(self.id, tags)
        if self._info is not None:
            self._info["tags"] = list(tags)

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
        self._info: Optional[dict] = None

    def _get_info(self) -> dict:
        """Get dataset info (cached)."""
        if self._info is None:
            self._info = self.storage._call("dataset_get", id=self.id)
        return self._info

    def get_info(self) -> dict:
        """Get dataset information."""
        return self._get_info()

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

    @property
    def tags(self) -> list[str]:
        """Get dataset tags."""
        return self._get_info().get("tags", [])

    def add_tag(self, tag: str) -> None:
        """Add a tag to this dataset."""
        self.storage.dataset_add_tags(self.id, [tag])
        if self._info is not None:
            if tag not in self._info.get("tags", []):
                self._info.setdefault("tags", []).append(tag)

    def remove_tag(self, tag: str) -> None:
        """Remove a tag from this dataset."""
        self.storage.dataset_remove_tags(self.id, [tag])
        if self._info is not None:
            if tag in self._info.get("tags", []):
                self._info["tags"].remove(tag)

    def set_tags(self, tags: list[str]) -> None:
        """Set tags for this dataset (replace all)."""
        self.storage.dataset_set_tags(self.id, tags)
        if self._info is not None:
            self._info["tags"] = list(tags)

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

    def __getitem__(self, slice_tuple):
        """Support NumPy-style slicing.

        Args:
            slice_tuple: Slice tuple (e.g., [0:2], [..., 0], etc.)

        Returns:
            Sliced array data
        """
        # Convert single index to tuple
        if not isinstance(slice_tuple, tuple):
            slice_tuple = (slice_tuple,)

        # Serialize slice parameters for transmission
        serialized_slices = []
        for s in slice_tuple:
            if isinstance(s, slice):
                serialized_slices.append({
                    "type": "slice",
                    "start": s.start,
                    "stop": s.stop,
                    "step": s.step,
                })
            elif isinstance(s, int):
                serialized_slices.append({"type": "int", "value": s})
            elif s is ...:
                serialized_slices.append({"type": "ellipsis"})
            else:
                serialized_slices.append({"type": "other", "value": s})

        return self.storage._call(
            "array_getitem_slice",
            dataset_id=self.dataset_id,
            key=self.key,
            slices=serialized_slices,
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
