"""Tests for Dataset class."""

from datetime import datetime

import numpy as np
import pytest

from qulab.storage.array import Array
from qulab.storage.dataset import Dataset
from qulab.storage.local import LocalStorage


class TestDataset:
    """Test Dataset class."""

    def test_create(self, local_storage: LocalStorage):
        """Test creating a dataset."""
        ref = Dataset.create(local_storage, "test_dataset", description={})

        assert ref.id is not None
        assert ref.name == "test_dataset"

        # Verify dataset exists
        dataset = ref.get()
        assert dataset is not None
        assert dataset.name == "test_dataset"

    def test_create_with_config(self, local_storage: LocalStorage, sample_config: dict):
        """Test creating a dataset with config."""
        ref = Dataset.create(
            local_storage,
            "test_dataset",
            description={"app": "test"},
            config=sample_config,
        )

        dataset = ref.get()
        assert dataset._config_hash is not None

    def test_create_with_script(self, local_storage: LocalStorage, sample_script: str):
        """Test creating a dataset with script."""
        ref = Dataset.create(
            local_storage,
            "test_dataset",
            description={"app": "test"},
            script=sample_script,
        )

        dataset = ref.get()
        assert dataset._script_hash is not None

    def test_create_with_config_and_script(
        self, local_storage: LocalStorage, sample_config: dict, sample_script: str
    ):
        """Test creating a dataset with both config and script."""
        ref = Dataset.create(
            local_storage,
            "test_dataset",
            description={"app": "test"},
            config=sample_config,
            script=sample_script,
        )

        dataset = ref.get()
        assert dataset._config_hash is not None
        assert dataset._script_hash is not None

    def test_load(self, local_storage: LocalStorage):
        """Test loading a dataset."""
        ref = Dataset.create(local_storage, "test_dataset", description={})
        dataset_id = ref.id

        # Load by ID
        loaded = Dataset.load(local_storage, dataset_id)
        assert loaded.name == "test_dataset"
        assert loaded.id == dataset_id

    def test_description(self, local_storage: LocalStorage):
        """Test getting description."""
        ref = Dataset.create(
            local_storage,
            "test_dataset",
            description={"app": "test_app", "version": "1.0"},
        )

        dataset = ref.get()
        desc = dataset.description
        assert desc == {"app": "test_app", "version": "1.0"}

    def test_config_lazy_load(
        self, local_storage: LocalStorage, sample_config: dict
    ):
        """Test config lazy loading."""
        ref = Dataset.create(
            local_storage,
            "test_dataset",
            description={"app": "test"},
            config=sample_config,
        )

        dataset = ref.get()
        # Config should not be loaded yet
        assert dataset._config is None

        # Access config property
        config = dataset.config
        assert config == sample_config
        assert dataset._config is not None  # Now cached

    def test_config_hash(self, local_storage: LocalStorage, sample_config: dict):
        """Test config hash value."""
        from qulab.storage.models.config import compute_config_hash

        ref = Dataset.create(
            local_storage,
            "test_dataset",
            description={},
            config=sample_config,
        )

        dataset = ref.get()
        expected_hash = compute_config_hash(sample_config)
        assert dataset.config_hash == expected_hash

    def test_script_lazy_load(
        self, local_storage: LocalStorage, sample_script: str
    ):
        """Test script lazy loading."""
        ref = Dataset.create(
            local_storage,
            "test_dataset",
            description={},
            script=sample_script,
        )

        dataset = ref.get()
        # Script should not be loaded yet
        assert dataset._script is None

        # Access script property
        script = dataset.script
        assert script == sample_script
        assert dataset._script is not None  # Now cached

    def test_script_hash(self, local_storage: LocalStorage, sample_script: str):
        """Test script hash value."""
        from qulab.storage.models.script import compute_script_hash

        ref = Dataset.create(
            local_storage,
            "test_dataset",
            description={},
            script=sample_script,
        )

        dataset = ref.get()
        expected_hash = compute_script_hash(sample_script)
        assert dataset.script_hash == expected_hash

    def test_keys(self, local_storage: LocalStorage):
        """Test getting array keys."""
        ref = Dataset.create(local_storage, "test_dataset", description={})
        dataset = ref.get()

        # Initially empty
        assert dataset.keys() == []

        # Create some arrays
        dataset.create_array("x", (1,))
        dataset.create_array("y", (1,))

        assert sorted(dataset.keys()) == ["x", "y"]

    def test_create_array(self, local_storage: LocalStorage):
        """Test creating an array."""
        ref = Dataset.create(local_storage, "test_dataset", description={})
        dataset = ref.get()

        array = dataset.create_array("test_array", (2, 3))

        assert isinstance(array, Array)
        assert array.name == "test_array"
        assert array.inner_shape == (2, 3)

    def test_get_array(self, local_storage: LocalStorage):
        """Test getting an array."""
        ref = Dataset.create(local_storage, "test_dataset", description={})
        dataset = ref.get()

        # Create array
        created = dataset.create_array("test_array", (1,))

        # Get it back
        retrieved = dataset.get_array("test_array")

        assert retrieved.name == created.name
        assert retrieved.inner_shape == created.inner_shape

    def test_get_array_not_found(self, local_storage: LocalStorage):
        """Test getting a non-existent array raises KeyError."""
        ref = Dataset.create(local_storage, "test_dataset", description={})
        dataset = ref.get()

        with pytest.raises(KeyError):
            dataset.get_array("nonexistent")

    def test_append(self, local_storage: LocalStorage):
        """Test appending data points."""
        ref = Dataset.create(local_storage, "test_dataset", description={})
        dataset = ref.get()

        # Append data
        dataset.append((0, 0), {"x": 1.0, "y": 2.0})

        # Arrays should be created automatically
        assert "x" in dataset.keys()
        assert "y" in dataset.keys()

        # Verify data
        x_array = dataset.get_array("x")
        items = list(x_array.iter())
        assert len(items) == 1
        assert items[0] == ((0, 0), 1.0)

    def test_append_auto_create_array(self, local_storage: LocalStorage):
        """Test that append auto-creates arrays."""
        ref = Dataset.create(local_storage, "test_dataset", description={})
        dataset = ref.get()

        # No arrays yet
        assert dataset.keys() == []

        # Append with numpy arrays - should infer inner_shape
        dataset.append((0, 0), {"data": np.array([1.0, 2.0, 3.0])})

        # Array should be created with inferred shape
        assert "data" in dataset.keys()
        data_array = dataset.get_array("data")
        assert data_array.inner_shape == (3,)

    def test_flush(self, local_storage: LocalStorage):
        """Test flushing data to disk."""
        ref = Dataset.create(local_storage, "test_dataset", description={})
        dataset = ref.get()

        # Append data
        dataset.append((0, 0), {"x": 1.0, "y": 2.0})
        dataset.append((0, 1), {"x": 3.0, "y": 4.0})

        # Flush
        dataset.flush()

        # All arrays should be flushed (Array uses _list as buffer)
        for key in dataset.keys():
            array = dataset.get_array(key)
            assert len(array._list) == 0

    def test_delete(self, local_storage: LocalStorage):
        """Test deleting a dataset."""
        ref = Dataset.create(local_storage, "test_dataset", description={})
        dataset_id = ref.id

        # Create some arrays
        dataset = ref.get()
        dataset.create_array("x", (1,))
        dataset.flush()

        # Delete
        assert ref.delete() is True

        # Should not be able to get it anymore
        with pytest.raises(KeyError):
            local_storage.get_dataset(dataset_id)

    def test_dataset_ref_get(self, local_storage: LocalStorage):
        """Test DatasetRef.get()."""
        ref = Dataset.create(local_storage, "test_dataset", description={})

        dataset = ref.get()
        assert isinstance(dataset, Dataset)
        assert dataset.name == "test_dataset"

    def test_dataset_ref_delete(self, local_storage: LocalStorage):
        """Test DatasetRef.delete()."""
        ref = Dataset.create(local_storage, "test_dataset", description={})
        dataset_id = ref.id

        result = ref.delete()
        assert result is True

        # Verify deletion
        with pytest.raises(KeyError):
            local_storage.get_dataset(dataset_id)

    def test_get_documents(self, local_storage: LocalStorage):
        """Test getting documents derived from dataset."""
        from qulab.storage.document import Document

        # Create dataset
        ds_ref = Dataset.create(local_storage, "source_dataset", description={})
        dataset = ds_ref.get()

        # Create document linked to dataset (pass dataset ID, not object)
        doc_ref = Document.create(
            local_storage,
            name="derived_doc",
            data={"result": "success"},
            datasets=[dataset.id],
        )

        # Get documents from dataset
        docs = dataset.get_documents()
        assert len(docs) == 1
        assert docs[0].name == "derived_doc"

    def test_to_dict(self, local_storage: LocalStorage):
        """Test converting to dictionary."""
        ref = Dataset.create(
            local_storage,
            "test_dataset",
            description={"app": "test"},
        )

        dataset = ref.get()
        data = dataset.to_dict()

        assert data["id"] == ref.id
        assert data["name"] == "test_dataset"
        assert data["description"] == {"app": "test"}
        assert "ctime" in data
        assert "mtime" in data

    def test_append_multiple_positions(self, local_storage: LocalStorage):
        """Test appending at multiple positions."""
        ref = Dataset.create(local_storage, "test_dataset", description={})
        dataset = ref.get()

        # Append at various positions
        positions = [(i, j) for i in range(3) for j in range(3)]
        for i, pos in enumerate(positions):
            dataset.append(pos, {"value": float(i)})

        # Verify all data
        value_array = dataset.get_array("value")
        items = list(value_array.iter())
        assert len(items) == 9

    def test_create_dataset_without_description(self, local_storage: LocalStorage):
        """Test creating dataset without explicit description."""
        ref = Dataset.create(local_storage, "test_dataset", description={})
        dataset = ref.get()

        assert dataset.description == {}

    def test_dataset_timestamps(self, local_storage: LocalStorage):
        """Test that dataset has timestamps."""
        ref = Dataset.create(local_storage, "test_dataset", description={})
        dataset = ref.get()

        assert isinstance(dataset.ctime, datetime)
        assert isinstance(dataset.mtime, datetime)
        assert isinstance(dataset.atime, datetime)


class TestDatasetTags:
    """Test Dataset tag editing functionality."""

    def test_create_with_tags(self, local_storage: LocalStorage):
        """Test creating a dataset with tags."""
        ref = Dataset.create(
            local_storage,
            name="test_dataset",
            description={"app": "test"},
            tags=["tag1", "tag2"],
        )

        dataset = ref.get()
        assert "tag1" in dataset.tags
        assert "tag2" in dataset.tags

    def test_add_tag(self, local_storage: LocalStorage):
        """Test adding a tag to a dataset."""
        ref = Dataset.create(
            local_storage,
            name="test_dataset",
            description={},
            tags=["initial"],
        )
        dataset = ref.get()

        # Add a new tag
        dataset.add_tag("new_tag")

        # Verify tag was added
        assert "new_tag" in dataset.tags
        assert "initial" in dataset.tags

        # Reload and verify
        reloaded = Dataset.load(local_storage, dataset.id)
        assert "new_tag" in reloaded.tags
        assert "initial" in reloaded.tags

    def test_add_duplicate_tag(self, local_storage: LocalStorage):
        """Test adding a duplicate tag is handled gracefully."""
        ref = Dataset.create(
            local_storage,
            name="test_dataset",
            description={},
            tags=["tag1"],
        )
        dataset = ref.get()

        # Add the same tag again
        dataset.add_tag("tag1")

        # Should not have duplicates
        assert dataset.tags.count("tag1") == 1

    def test_remove_tag(self, local_storage: LocalStorage):
        """Test removing a tag from a dataset."""
        ref = Dataset.create(
            local_storage,
            name="test_dataset",
            description={},
            tags=["tag1", "tag2", "tag3"],
        )
        dataset = ref.get()

        # Remove a tag
        dataset.remove_tag("tag2")

        # Verify tag was removed
        assert "tag2" not in dataset.tags
        assert "tag1" in dataset.tags
        assert "tag3" in dataset.tags

        # Reload and verify
        reloaded = Dataset.load(local_storage, dataset.id)
        assert "tag2" not in reloaded.tags
        assert "tag1" in reloaded.tags
        assert "tag3" in reloaded.tags

    def test_remove_nonexistent_tag(self, local_storage: LocalStorage):
        """Test removing a tag that doesn't exist."""
        ref = Dataset.create(
            local_storage,
            name="test_dataset",
            description={},
            tags=["tag1"],
        )
        dataset = ref.get()

        # Remove a non-existent tag (should not raise)
        dataset.remove_tag("nonexistent")

        # Original tags should remain
        assert "tag1" in dataset.tags

    def test_set_tags(self, local_storage: LocalStorage):
        """Test setting tags (replace all)."""
        ref = Dataset.create(
            local_storage,
            name="test_dataset",
            description={},
            tags=["old1", "old2"],
        )
        dataset = ref.get()

        # Set new tags
        dataset.set_tags(["new1", "new2", "new3"])

        # Verify tags were replaced
        assert set(dataset.tags) == {"new1", "new2", "new3"}

        # Reload and verify
        reloaded = Dataset.load(local_storage, dataset.id)
        assert set(reloaded.tags) == {"new1", "new2", "new3"}

    def test_set_tags_empty(self, local_storage: LocalStorage):
        """Test setting empty tags list."""
        ref = Dataset.create(
            local_storage,
            name="test_dataset",
            description={},
            tags=["tag1", "tag2"],
        )
        dataset = ref.get()

        # Clear all tags
        dataset.set_tags([])

        # Verify tags were cleared
        assert dataset.tags == []

        # Reload and verify
        reloaded = Dataset.load(local_storage, dataset.id)
        assert reloaded.tags == []

    def test_storage_dataset_add_tags(self, local_storage: LocalStorage):
        """Test LocalStorage.dataset_add_tags()."""
        ref = Dataset.create(
            local_storage,
            name="test_dataset",
            description={},
            tags=["initial"],
        )

        # Add tags via storage
        local_storage.dataset_add_tags(ref.id, ["tag1", "tag2"])

        # Verify
        dataset = ref.get()
        assert "initial" in dataset.tags
        assert "tag1" in dataset.tags
        assert "tag2" in dataset.tags

    def test_storage_dataset_remove_tags(self, local_storage: LocalStorage):
        """Test LocalStorage.dataset_remove_tags()."""
        ref = Dataset.create(
            local_storage,
            name="test_dataset",
            description={},
            tags=["tag1", "tag2", "tag3"],
        )

        # Remove tags via storage
        local_storage.dataset_remove_tags(ref.id, ["tag2"])

        # Verify
        dataset = ref.get()
        assert "tag1" in dataset.tags
        assert "tag2" not in dataset.tags
        assert "tag3" in dataset.tags

    def test_storage_dataset_set_tags(self, local_storage: LocalStorage):
        """Test LocalStorage.dataset_set_tags()."""
        ref = Dataset.create(
            local_storage,
            name="test_dataset",
            description={},
            tags=["old1", "old2"],
        )

        # Set tags via storage
        local_storage.dataset_set_tags(ref.id, ["new1", "new2"])

        # Verify
        dataset = ref.get()
        assert set(dataset.tags) == {"new1", "new2"}

    def test_tag_query_after_edit(self, local_storage: LocalStorage):
        """Test that query by tag works after editing tags."""
        ref = Dataset.create(
            local_storage,
            name="test_dataset",
            description={},
            tags=["initial"],
        )

        # Add tag
        dataset = ref.get()
        dataset.add_tag("searchable")

        # Query by new tag
        results = list(local_storage.query_datasets(tags=["searchable"]))
        assert len(results) == 1
        assert results[0].id == ref.id

        # Remove tag
        dataset.remove_tag("searchable")

        # Query again
        results = list(local_storage.query_datasets(tags=["searchable"]))
        assert len(results) == 0
