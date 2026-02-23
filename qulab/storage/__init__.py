"""QuLab unified storage system.

This module provides unified storage for:
- Documents: Workflow reports and general document storage (replaces executor.storage)
- Datasets: Scan/experiment data storage (replaces scan.record)
- Arrays: Multidimensional array storage (replaces BufferList)

Example:
    >>> from qulab.storage import LocalStorage
    >>> storage = LocalStorage("/path/to/storage")
    >>>
    >>> # Create a document
    >>> doc_ref = storage.create_document(
    ...     name="calibration",
    ...     data={"f01": 5.2e9},
    ...     state="ok",
    ...     tags=["calibration", "qubit"]
    ... )
    >>>
    >>> # Create a dataset
    >>> ds_ref = storage.create_dataset("scan1", {"app": "test"})
    >>> ds = ds_ref.get()
    >>> ds.append((0, 0), {"x": 1.0, "y": 2.0})
    >>> ds.flush()
"""

from .array import Array
from .base import Storage
from .dataset import Dataset
from .document import Document
from .local import DatasetRef, DocumentRef, LocalStorage

# Optional: remote storage (requires zmq)
try:
    from .remote import (
        RemoteArray,
        RemoteDataset,
        RemoteDatasetRef,
        RemoteDocument,
        RemoteDocumentRef,
        RemoteStorage,
    )
except ImportError:
    pass

# Optional: server (requires zmq, asyncio)
try:
    from .server import StorageServer
except ImportError:
    pass

__all__ = [
    # Base classes
    "Storage",
    # Local storage
    "LocalStorage",
    "DocumentRef",
    "DatasetRef",
    # Data classes
    "Document",
    "Dataset",
    "Array",
    # Remote storage (optional)
    "RemoteStorage",
    "RemoteDocumentRef",
    "RemoteDocument",
    "RemoteDatasetRef",
    "RemoteDataset",
    "RemoteArray",
    # Server (optional)
    "StorageServer",
]
