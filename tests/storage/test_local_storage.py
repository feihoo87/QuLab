"""Tests for LocalStorage class."""

import pytest
from pathlib import Path

from qulab.storage.local import LocalStorage, DocumentRef, DatasetRef
from qulab.storage.document import Document
from qulab.storage.datastore import Dataset


class TestLocalStorage:
    """Test LocalStorage class."""

    def test_init(self, temp_storage_path: Path):
        """Test storage initialization."""
        storage = LocalStorage(base_path=temp_storage_path)

        # Check directory structure
        assert (temp_storage_path / "documents").exists()
        assert (temp_storage_path / "datasets").exists()
        assert (temp_storage_path / "chunks").exists()

        # Check database file exists (using SQLite default)
        db_path = temp_storage_path / "storage.db"
        assert db_path.exists()

    def test_is_remote(self, local_storage: LocalStorage):
        """Verify is_remote returns False."""
        assert local_storage.is_remote is False

    def test_create_document(self, local_storage: LocalStorage, sample_document_data: dict):
        """Test creating a document."""
        ref = local_storage.create_document(
            name="test_doc",
            data=sample_document_data,
            state="ok",
            tags=["tag1", "tag2"],
        )

        assert isinstance(ref, DocumentRef)
        assert ref.id is not None
        assert ref.name == "test_doc"

    def test_get_document(self, local_storage: LocalStorage):
        """Test getting a created document."""
        # Create document
        ref = local_storage.create_document(
            name="test_doc",
            data={"key": "value"},
            state="ok",
        )

        # Get it back
        doc = local_storage.get_document(ref.id)
        assert isinstance(doc, Document)
        assert doc.name == "test_doc"
        assert doc.data == {"key": "value"}

    def test_get_document_not_found(self, local_storage: LocalStorage):
        """Test getting a non-existent document raises KeyError."""
        with pytest.raises(KeyError):
            local_storage.get_document(99999)

    def test_query_documents(self, local_storage: LocalStorage):
        """Test querying documents."""
        # Create documents
        local_storage.create_document(name="doc1", data={}, state="ok", tags=["tag1"])
        local_storage.create_document(name="doc2", data={}, state="error", tags=["tag2"])
        local_storage.create_document(name="doc3", data={}, state="ok", tags=["tag1", "tag2"])

        # Query all
        all_docs = list(local_storage.query_documents())
        assert len(all_docs) == 3

        # Query by name
        docs_by_name = list(local_storage.query_documents(name="doc1"))
        assert len(docs_by_name) == 1
        assert docs_by_name[0].name == "doc1"

        # Query by state
        ok_docs = list(local_storage.query_documents(state="ok"))
        assert len(ok_docs) == 2

        # Query by tags
        tag1_docs = list(local_storage.query_documents(tags=["tag1"]))
        assert len(tag1_docs) == 2

        # Query with limit
        limited = list(local_storage.query_documents(limit=2))
        assert len(limited) == 2

    def test_count_documents(self, local_storage: LocalStorage):
        """Test counting documents."""
        # Initially empty
        assert local_storage.count_documents() == 0

        # Create documents
        local_storage.create_document(name="doc1", data={}, state="ok")
        local_storage.create_document(name="doc2", data={}, state="error")

        # Count all
        assert local_storage.count_documents() == 2

        # Count by state
        assert local_storage.count_documents(state="ok") == 1
        assert local_storage.count_documents(state="error") == 1

    def test_create_dataset(self, local_storage: LocalStorage):
        """Test creating a dataset."""
        ref = local_storage.create_dataset(
            name="test_dataset",
            description={"app": "test"},
        )

        assert isinstance(ref, DatasetRef)
        assert ref.id is not None
        assert ref.name == "test_dataset"

    def test_get_dataset(self, local_storage: LocalStorage):
        """Test getting a created dataset."""
        # Create dataset
        ref = local_storage.create_dataset(
            name="test_dataset",
            description={"app": "test"},
        )

        # Get it back
        dataset = local_storage.get_dataset(ref.id)
        assert isinstance(dataset, Dataset)
        assert dataset.name == "test_dataset"

    def test_get_dataset_not_found(self, local_storage: LocalStorage):
        """Test getting a non-existent dataset raises KeyError."""
        with pytest.raises(KeyError):
            local_storage.get_dataset(99999)

    def test_query_datasets(self, local_storage: LocalStorage):
        """Test querying datasets."""
        # Create datasets
        local_storage.create_dataset(name="ds1", description={})
        local_storage.create_dataset(name="ds2", description={})
        local_storage.create_dataset(name="ds3", description={})

        # Query all
        all_ds = list(local_storage.query_datasets())
        assert len(all_ds) == 3

        # Query by name
        ds_by_name = list(local_storage.query_datasets(name="ds1"))
        assert len(ds_by_name) == 1

        # Query with limit
        limited = list(local_storage.query_datasets(limit=2))
        assert len(limited) == 2

    def test_count_datasets(self, local_storage: LocalStorage):
        """Test counting datasets."""
        # Initially empty
        assert local_storage.count_datasets() == 0

        # Create datasets
        local_storage.create_dataset(name="ds1", description={})
        local_storage.create_dataset(name="ds2", description={})

        # Count all
        assert local_storage.count_datasets() == 2

    def test_query_documents_by_time(self, local_storage: LocalStorage):
        """Test querying documents by time range."""
        from datetime import datetime, timedelta, timezone

        # Create documents
        ref1 = local_storage.create_document(name="doc1", data={})
        ref2 = local_storage.create_document(name="doc2", data={})

        # Query by time range (using after/before parameters)
        start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        docs = list(local_storage.query_documents(after=start_time))
        assert len(docs) == 2

        # Query by end time
        end_time = datetime.now(timezone.utc) + timedelta(hours=1)
        docs = list(local_storage.query_documents(before=end_time))
        assert len(docs) == 2

    def test_query_datasets_by_time(self, local_storage: LocalStorage):
        """Test querying datasets by time range."""
        from datetime import datetime, timedelta, timezone

        # Create datasets
        ref1 = local_storage.create_dataset(name="ds1", description={})
        ref2 = local_storage.create_dataset(name="ds2", description={})

        # Query by time range (using after/before parameters)
        start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        datasets = list(local_storage.query_datasets(after=start_time))
        assert len(datasets) == 2

        # Query by end time
        end_time = datetime.now(timezone.utc) + timedelta(hours=1)
        datasets = list(local_storage.query_datasets(before=end_time))
        assert len(datasets) == 2

    def test_create_document_with_script(self, local_storage: LocalStorage, sample_script: str):
        """Test creating document with script."""
        ref = local_storage.create_document(
            name="test_doc",
            data={"key": "value"},
            script=sample_script,
        )

        doc = ref.get()
        assert doc.script == sample_script

    def test_create_dataset_with_config(self, local_storage: LocalStorage, sample_config: dict):
        """Test creating dataset with config."""
        ref = local_storage.create_dataset(
            name="test_dataset",
            description={},
            config=sample_config,
        )

        dataset = ref.get()
        assert dataset.config == sample_config

    def test_create_dataset_with_script(self, local_storage: LocalStorage, sample_script: str):
        """Test creating dataset with script."""
        ref = local_storage.create_dataset(
            name="test_dataset",
            description={},
            script=sample_script,
        )

        dataset = ref.get()
        assert dataset.script == sample_script

    def test_document_ref_delete(self, local_storage: LocalStorage):
        """Test DocumentRef.delete()."""
        ref = local_storage.create_document(name="test_doc", data={})
        doc_id = ref.id

        # Delete
        assert ref.delete() is True

        # Should not exist anymore
        with pytest.raises(KeyError):
            local_storage.get_document(doc_id)

    def test_dataset_ref_delete(self, local_storage: LocalStorage):
        """Test DatasetRef.delete()."""
        ref = local_storage.create_dataset(name="test_dataset", description={})
        ds_id = ref.id

        # Delete
        assert ref.delete() is True

        # Should not exist anymore
        with pytest.raises(KeyError):
            local_storage.get_dataset(ds_id)

    def test_storage_custom_db_url(self, temp_storage_path: Path):
        """Test storage with custom database URL."""
        custom_db = temp_storage_path / "custom.db"
        storage = LocalStorage(
            base_path=temp_storage_path,
            db_url=f"sqlite:///{custom_db}",
        )

        # Create a document
        ref = storage.create_document(name="test", data={})
        assert ref.id is not None

        # Verify custom DB file exists
        assert custom_db.exists()

    def test_document_with_tags(self, local_storage: LocalStorage):
        """Test document creation with tags."""
        ref = local_storage.create_document(
            name="tagged_doc",
            data={},
            tags=["important", "review", "urgent"],
        )

        # Query by single tag
        docs = list(local_storage.query_documents(tags=["important"]))
        assert len(docs) == 1

        # Query by multiple tags
        docs = list(local_storage.query_documents(tags=["important", "review"]))
        assert len(docs) == 1

        # Query by non-existent tag
        docs = list(local_storage.query_documents(tags=["nonexistent"]))
        assert len(docs) == 0

    def test_dataset_with_tags(self, local_storage: LocalStorage):
        """Test dataset creation with tags."""
        ref = local_storage.create_dataset(
            name="tagged_dataset",
            description={},
            tags=["experimental", "qubit1"],
        )

        # Query by single tag
        datasets = list(local_storage.query_datasets(tags=["experimental"]))
        assert len(datasets) == 1

        # Query by multiple tags
        datasets = list(local_storage.query_datasets(tags=["experimental", "qubit1"]))
        assert len(datasets) == 1

        # Query by non-existent tag
        datasets = list(local_storage.query_datasets(tags=["nonexistent"]))
        assert len(datasets) == 0

    def test_multiple_document_versions(self, local_storage: LocalStorage):
        """Test creating multiple document versions."""
        # Create first version
        v1 = local_storage.create_document(
            name="versioned_doc",
            data={"v": 1},
        )

        # Create second version
        v2 = local_storage.create_document(
            name="versioned_doc",
            data={"v": 2},
            parent_id=v1.id,
        )

        # Create third version
        v3 = local_storage.create_document(
            name="versioned_doc",
            data={"v": 3},
            parent_id=v2.id,
        )

        # Query all
        all_versions = list(local_storage.query_documents(name="versioned_doc"))
        assert len(all_versions) == 3

        # Verify chain
        doc3 = local_storage.get_document(v3.id)
        assert doc3.parent_id == v2.id

    def test_query_with_limit_and_offset(self, local_storage: LocalStorage):
        """Test query with limit."""
        # Create multiple documents
        for i in range(10):
            local_storage.create_document(name=f"doc_{i}", data={"index": i})

        # Query with limit
        limited = list(local_storage.query_documents(limit=5))
        assert len(limited) == 5

        # Query all
        all_docs = list(local_storage.query_documents())
        assert len(all_docs) == 10

    def test_state_transitions(self, local_storage: LocalStorage):
        """Test document state transitions."""
        # Create document with various states
        ref1 = local_storage.create_document(name="doc1", data={}, state="ok")
        ref2 = local_storage.create_document(name="doc2", data={}, state="error")
        ref3 = local_storage.create_document(name="doc3", data={}, state="warning")
        ref4 = local_storage.create_document(name="doc4", data={}, state="unknown")

        # Query by each state
        assert local_storage.count_documents(state="ok") == 1
        assert local_storage.count_documents(state="error") == 1
        assert local_storage.count_documents(state="warning") == 1
        assert local_storage.count_documents(state="unknown") == 1

        # Verify document states
        assert local_storage.get_document(ref1.id).state == "ok"
        assert local_storage.get_document(ref2.id).state == "error"
        assert local_storage.get_document(ref3.id).state == "warning"
        assert local_storage.get_document(ref4.id).state == "unknown"

    def test_get_latest_document(self, local_storage: LocalStorage):
        """Test get_latest_document method."""
        from qulab.storage.local import DocumentRef

        # Create documents with the same name
        ref1 = local_storage.create_document(name="versioned_doc", data={"v": 1}, state="ok")
        ref2 = local_storage.create_document(name="versioned_doc", data={"v": 2}, state="ok")
        ref3 = local_storage.create_document(name="versioned_doc", data={"v": 3}, state="error")

        # Get latest without state filter
        latest = local_storage.get_latest_document(name="versioned_doc")
        assert latest is not None
        assert isinstance(latest, DocumentRef)
        assert latest.name == "versioned_doc"

        # Load the document and verify it's the latest
        doc = latest.get()
        assert doc.data == {"v": 3}
        assert doc.state == "error"

        # Get latest with state filter
        latest_ok = local_storage.get_latest_document(name="versioned_doc", state="ok")
        assert latest_ok is not None
        doc_ok = latest_ok.get()
        assert doc_ok.data == {"v": 2}
        assert doc_ok.state == "ok"

        # Get latest for non-existent name
        not_found = local_storage.get_latest_document(name="nonexistent")
        assert not_found is None

        # Get latest with state filter that matches nothing
        not_found_state = local_storage.get_latest_document(name="versioned_doc", state="unknown")
        assert not_found_state is None
