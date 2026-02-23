"""Storage abstract base class - defines the interface for all storage implementations."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Iterator, List, Optional, Union

if TYPE_CHECKING:
    from datetime import datetime

    from .dataset import Dataset, DatasetRef
    from .document import Document, DocumentRef


class Storage(ABC):
    """Abstract base class for storage implementations.

    This defines the common interface for both LocalStorage and RemoteStorage.
    All storage implementations should inherit from this class.
    """

    @property
    @abstractmethod
    def is_remote(self) -> bool:
        """Return True if this is a remote storage implementation."""
        pass

    # Document API
    @abstractmethod
    def create_document(
        self,
        name: str,
        data: dict,
        state: str = "unknown",
        tags: Optional[List[str]] = None,
        script: Optional[str] = None,
        **meta,
    ) -> "DocumentRef":
        """Create a new document.

        Args:
            name: Document name
            data: Document data dictionary
            state: Document state ('ok', 'error', 'warning', 'unknown')
            tags: List of tags for the document
            script: Optional script code string
            **meta: Additional metadata

        Returns:
            DocumentRef for the created document
        """
        pass

    @abstractmethod
    def get_document(self, id: int) -> "Document":
        """Get a document by ID.

        Args:
            id: Document ID

        Returns:
            Document instance

        Raises:
            KeyError: If document not found
        """
        pass

    @abstractmethod
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
        """Query documents with filters.

        Args:
            name: Name pattern (supports * wildcard)
            tags: List of required tags
            state: Filter by state
            before: Created before this time
            after: Created after this time
            offset: Query offset
            limit: Maximum results

        Yields:
            DocumentRef instances matching the filters
        """
        pass

    @abstractmethod
    def count_documents(
        self,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        state: Optional[str] = None,
        before: Optional["datetime"] = None,
        after: Optional["datetime"] = None,
    ) -> int:
        """Count documents matching filters.

        Args:
            name: Name pattern
            tags: List of required tags
            state: Filter by state
            before: Created before this time
            after: Created after this time

        Returns:
            Number of matching documents
        """
        pass

    # Dataset API
    @abstractmethod
    def create_dataset(
        self,
        name: str,
        description: dict,
        config: Optional[dict] = None,
        script: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> "DatasetRef":
        """Create a new dataset.

        Args:
            name: Dataset name
            description: Dataset description dictionary
            config: Optional configuration dictionary
            script: Optional script code string
            tags: Optional list of tags

        Returns:
            DatasetRef for the created dataset
        """
        pass

    @abstractmethod
    def get_dataset(self, id: int) -> "Dataset":
        """Get a dataset by ID.

        Args:
            id: Dataset ID

        Returns:
            Dataset instance

        Raises:
            KeyError: If dataset not found
        """
        pass

    @abstractmethod
    def query_datasets(
        self,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        before: Optional["datetime"] = None,
        after: Optional["datetime"] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Iterator["DatasetRef"]:
        """Query datasets with filters.

        Args:
            name: Name pattern (supports * wildcard)
            tags: List of required tags
            before: Created before this time
            after: Created after this time
            offset: Query offset
            limit: Maximum results

        Yields:
            DatasetRef instances matching the filters
        """
        pass

    @abstractmethod
    def count_datasets(
        self,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        before: Optional["datetime"] = None,
        after: Optional["datetime"] = None,
    ) -> int:
        """Count datasets matching filters.

        Args:
            name: Name pattern
            tags: List of required tags
            before: Created before this time
            after: Created after this time

        Returns:
            Number of matching datasets
        """
        pass
