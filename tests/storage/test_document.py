"""Tests for Document class."""

from datetime import datetime

import pytest

from qulab.storage.dataset import Dataset
from qulab.storage.document import Document
from qulab.storage.local import LocalStorage


class TestDocument:
    """Test Document class."""

    def test_create(self, local_storage: LocalStorage, sample_document_data: dict):
        """Test creating a document."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data=sample_document_data,
            state="ok",
        )

        assert ref.id is not None
        assert ref.name == "test_doc"

        # Verify document exists
        doc = ref.get()
        assert doc is not None
        assert doc.name == "test_doc"
        assert doc.data == sample_document_data
        assert doc.state == "ok"

    def test_create_with_script(self, local_storage: LocalStorage, sample_script: str):
        """Test creating a document with script."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"result": "success"},
            script=sample_script,
        )

        doc = ref.get()
        assert doc._script_hash is not None
        assert doc.script == sample_script

    def test_create_with_tags(self, local_storage: LocalStorage, sample_tags: list):
        """Test creating a document with tags."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"key": "value"},
            tags=sample_tags,
        )

        doc = ref.get()
        assert doc.tags == sample_tags

    def test_create_with_parent(self, local_storage: LocalStorage):
        """Test creating a document with parent (version chain)."""
        # Create parent document
        parent_ref = Document.create(
            local_storage,
            name="versioned_doc",
            data={"version": 1},
            state="ok",
        )
        parent = parent_ref.get()

        # Create child document
        child_ref = Document.create(
            local_storage,
            name="versioned_doc",
            data={"version": 2},
            state="ok",
            parent_id=parent.id,
        )
        child = child_ref.get()

        assert child.parent_id == parent.id
        assert child.version == parent.version + 1

    def test_create_with_datasets(self, local_storage: LocalStorage):
        """Test creating a document associated with datasets."""
        # Create datasets
        ds1_ref = Dataset.create(local_storage, "dataset1", description={})
        ds2_ref = Dataset.create(local_storage, "dataset2", description={})
        ds1 = ds1_ref.get()
        ds2 = ds2_ref.get()

        # Create document with datasets (pass dataset IDs, not objects)
        ref = Document.create(
            local_storage,
            name="analysis_doc",
            data={"analysis": "results"},
            datasets=[ds1.id, ds2.id],
        )

        doc = ref.get()
        ids = doc.dataset_ids
        assert len(ids) == 2
        assert ds1.id in ids
        assert ds2.id in ids

    def test_load(self, local_storage: LocalStorage, sample_document_data: dict):
        """Test loading a document."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data=sample_document_data,
            state="ok",
        )
        doc_id = ref.id

        # Load by ID
        loaded = Document.load(local_storage, doc_id)
        assert loaded.name == "test_doc"
        assert loaded.data == sample_document_data
        assert loaded.state == "ok"
        assert loaded.id == doc_id

    def test_script_lazy_load(self, local_storage: LocalStorage, sample_script: str):
        """Test script lazy loading."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"key": "value"},
            script=sample_script,
        )

        doc = ref.get()
        # Script should not be loaded yet
        assert doc._script is None

        # Access script property
        script = doc.script
        assert script == sample_script
        assert doc._script is not None  # Now cached

    def test_script_hash(self, local_storage: LocalStorage, sample_script: str):
        """Test script hash value."""
        from qulab.storage.models.script import compute_script_hash

        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"key": "value"},
            script=sample_script,
        )

        doc = ref.get()
        expected_hash = compute_script_hash(sample_script)
        assert doc.script_hash == expected_hash

    def test_save(self, local_storage: LocalStorage):
        """Test saving as new version."""
        # Create initial document
        ref = Document.create(
            local_storage,
            name="versioned_doc",
            data={"version": 1, "content": "original"},
            state="ok",
        )
        doc = ref.get()
        original_id = doc.id
        original_version = doc.version

        # Modify and save
        doc.data["content"] = "updated"
        doc.state = "error"
        new_ref = doc.save(local_storage)
        new_doc = new_ref.get()

        # Should be new version
        assert new_doc.id != original_id
        assert new_doc.version == original_version + 1
        assert new_doc.parent_id == original_id
        assert new_doc.data["content"] == "updated"
        assert new_doc.state == "error"

    def test_to_dict(self, local_storage: LocalStorage, sample_document_data: dict):
        """Test converting to dictionary."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data=sample_document_data,
            state="ok",
            tags=["tag1", "tag2"],
        )

        doc = ref.get()
        data = doc.to_dict()

        assert data["id"] == ref.id
        assert data["name"] == "test_doc"
        assert data["data"] == sample_document_data
        assert data["state"] == "ok"
        assert data["tags"] == ["tag1", "tag2"]
        assert data["version"] == 1
        assert "ctime" in data
        assert "mtime" in data

    def test_from_dict(self, local_storage: LocalStorage):
        """Test creating from dictionary."""
        data = {
            "id": 123,
            "name": "restored_doc",
            "data": {"key": "value"},
            "meta": {"extra": "info"},
            "ctime": "2024-01-01T00:00:00",
            "mtime": "2024-01-01T12:00:00",
            "atime": "2024-01-01T12:00:00",
            "tags": ["tag1"],
            "state": "ok",
            "version": 2,
            "parent_id": 100,
            "_dataset_ids": [1, 2, 3],
            "_script": "def test(): pass",
            "_script_hash": "abc123",
        }

        doc = Document.from_dict(data)

        assert doc.id == 123
        assert doc.name == "restored_doc"
        assert doc.data == {"key": "value"}
        assert doc.meta == {"extra": "info"}
        assert doc.state == "ok"
        assert doc.version == 2
        assert doc.parent_id == 100
        assert doc.tags == ["tag1"]
        assert doc._dataset_ids == [1, 2, 3]
        assert doc._script == "def test(): pass"
        assert doc._script_hash == "abc123"

    def test_document_ref_get(self, local_storage: LocalStorage):
        """Test DocumentRef.get()."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"key": "value"},
        )

        doc = ref.get()
        assert isinstance(doc, Document)
        assert doc.name == "test_doc"

    def test_document_ref_delete(self, local_storage: LocalStorage):
        """Test DocumentRef.delete()."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"key": "value"},
        )
        doc_id = ref.id

        result = ref.delete()
        assert result is True

        # Verify deletion
        with pytest.raises(KeyError):
            local_storage.get_document(doc_id)

    def test_get_datasets(self, local_storage: LocalStorage):
        """Test getting associated datasets."""
        # Create dataset
        ds_ref = Dataset.create(local_storage, "source_dataset", description={})
        dataset = ds_ref.get()

        # Create document with dataset (pass ID, not object)
        ref = Document.create(
            local_storage,
            name="analysis_doc",
            data={"analysis": "results"},
            datasets=[dataset.id],
        )

        doc = ref.get()
        datasets = doc.get_datasets(local_storage)
        assert len(datasets) == 1
        assert datasets[0].name == "source_dataset"

    def test_get_dataset_ids(self, local_storage: LocalStorage):
        """Test getting dataset IDs."""
        ds_ref = Dataset.create(local_storage, "dataset", description={})
        dataset = ds_ref.get()

        ref = Document.create(
            local_storage,
            name="doc",
            data={},
            datasets=[dataset.id],
        )

        doc = ref.get()
        ids = doc.dataset_ids
        assert ids == [dataset.id]

    def test_document_without_script(self, local_storage: LocalStorage):
        """Test document without script."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"key": "value"},
        )

        doc = ref.get()
        assert doc.script is None
        assert doc.script_hash is None

    def test_document_meta(self, local_storage: LocalStorage):
        """Test document with additional metadata."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"key": "value"},
            author="test_user",
            priority="high",
        )

        doc = ref.get()
        assert doc.meta.get("author") == "test_user"
        assert doc.meta.get("priority") == "high"

    def test_document_timestamps(self, local_storage: LocalStorage):
        """Test document timestamps."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"key": "value"},
        )

        doc = ref.get()
        assert isinstance(doc.ctime, datetime)
        assert isinstance(doc.mtime, datetime)
        assert isinstance(doc.atime, datetime)

    def test_version_chain_multiple(self, local_storage: LocalStorage):
        """Test creating multiple versions in a chain."""
        # Create first version
        v1_ref = Document.create(
            local_storage,
            name="versioned_doc",
            data={"version": 1},
        )
        v1 = v1_ref.get()

        # Create second version
        v2_ref = Document.create(
            local_storage,
            name="versioned_doc",
            data={"version": 2},
            parent_id=v1.id,
        )
        v2 = v2_ref.get()

        # Create third version
        v3_ref = Document.create(
            local_storage,
            name="versioned_doc",
            data={"version": 3},
            parent_id=v2.id,
        )
        v3 = v3_ref.get()

        assert v1.version == 1
        assert v2.version == 2
        assert v3.version == 3
        assert v2.parent_id == v1.id
        assert v3.parent_id == v2.id


class TestDocumentTags:
    """Test Document tag editing functionality."""

    def test_add_tag(self, local_storage: LocalStorage):
        """Test adding a tag to a document."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"key": "value"},
            tags=["initial"],
        )
        doc = ref.get()

        # Add a new tag
        doc.add_tag("new_tag")

        # Verify tag was added
        assert "new_tag" in doc.tags
        assert "initial" in doc.tags

        # Reload and verify
        reloaded = Document.load(local_storage, doc.id)
        assert "new_tag" in reloaded.tags
        assert "initial" in reloaded.tags

    def test_add_duplicate_tag(self, local_storage: LocalStorage):
        """Test adding a duplicate tag is handled gracefully."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"key": "value"},
            tags=["tag1"],
        )
        doc = ref.get()

        # Add the same tag again
        doc.add_tag("tag1")

        # Should not have duplicates
        assert doc.tags.count("tag1") == 1

    def test_remove_tag(self, local_storage: LocalStorage):
        """Test removing a tag from a document."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"key": "value"},
            tags=["tag1", "tag2", "tag3"],
        )
        doc = ref.get()

        # Remove a tag
        doc.remove_tag("tag2")

        # Verify tag was removed
        assert "tag2" not in doc.tags
        assert "tag1" in doc.tags
        assert "tag3" in doc.tags

        # Reload and verify
        reloaded = Document.load(local_storage, doc.id)
        assert "tag2" not in reloaded.tags
        assert "tag1" in reloaded.tags
        assert "tag3" in reloaded.tags

    def test_remove_nonexistent_tag(self, local_storage: LocalStorage):
        """Test removing a tag that doesn't exist."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"key": "value"},
            tags=["tag1"],
        )
        doc = ref.get()

        # Remove a non-existent tag (should not raise)
        doc.remove_tag("nonexistent")

        # Original tags should remain
        assert "tag1" in doc.tags

    def test_set_tags(self, local_storage: LocalStorage):
        """Test setting tags (replace all)."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"key": "value"},
            tags=["old1", "old2"],
        )
        doc = ref.get()

        # Set new tags
        doc.set_tags(["new1", "new2", "new3"])

        # Verify tags were replaced
        assert doc.tags == ["new1", "new2", "new3"]

        # Reload and verify
        reloaded = Document.load(local_storage, doc.id)
        assert set(reloaded.tags) == {"new1", "new2", "new3"}

    def test_set_tags_empty(self, local_storage: LocalStorage):
        """Test setting empty tags list."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"key": "value"},
            tags=["tag1", "tag2"],
        )
        doc = ref.get()

        # Clear all tags
        doc.set_tags([])

        # Verify tags were cleared
        assert doc.tags == []

        # Reload and verify
        reloaded = Document.load(local_storage, doc.id)
        assert reloaded.tags == []

    def test_storage_document_add_tags(self, local_storage: LocalStorage):
        """Test LocalStorage.document_add_tags()."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"key": "value"},
            tags=["initial"],
        )

        # Add tags via storage
        local_storage.document_add_tags(ref.id, ["tag1", "tag2"])

        # Verify
        doc = ref.get()
        assert "initial" in doc.tags
        assert "tag1" in doc.tags
        assert "tag2" in doc.tags

    def test_storage_document_remove_tags(self, local_storage: LocalStorage):
        """Test LocalStorage.document_remove_tags()."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"key": "value"},
            tags=["tag1", "tag2", "tag3"],
        )

        # Remove tags via storage
        local_storage.document_remove_tags(ref.id, ["tag2"])

        # Verify
        doc = ref.get()
        assert "tag1" in doc.tags
        assert "tag2" not in doc.tags
        assert "tag3" in doc.tags

    def test_storage_document_set_tags(self, local_storage: LocalStorage):
        """Test LocalStorage.document_set_tags()."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"key": "value"},
            tags=["old1", "old2"],
        )

        # Set tags via storage
        local_storage.document_set_tags(ref.id, ["new1", "new2"])

        # Verify
        doc = ref.get()
        assert set(doc.tags) == {"new1", "new2"}

    def test_tag_query_after_edit(self, local_storage: LocalStorage):
        """Test that query by tag works after editing tags."""
        ref = Document.create(
            local_storage,
            name="test_doc",
            data={"key": "value"},
            tags=["initial"],
        )

        # Add tag
        doc = ref.get()
        doc.add_tag("searchable")

        # Query by new tag
        results = list(local_storage.query_documents(tags=["searchable"]))
        assert len(results) == 1
        assert results[0].id == ref.id

        # Remove tag
        doc.remove_tag("searchable")

        # Query again
        results = list(local_storage.query_documents(tags=["searchable"]))
        assert len(results) == 0
