"""Tests for storage models."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from qulab.storage.models.base import SessionManager
from qulab.storage.models.config import (
    Config,
    compute_config_hash,
    decrement_config_ref,
    get_or_create_config,
    increment_config_ref,
    load_config,
    save_config,
)
from qulab.storage.models.dataset import Array, Dataset
from qulab.storage.models.document import Document, document_datasets
from qulab.storage.models.script import (
    Script,
    compute_script_hash,
    decrement_script_ref,
    get_or_create_script,
    increment_script_ref,
    load_script,
    save_script,
)
from qulab.storage.models.tag import Tag, get_object_with_tags, get_or_create_tag, has_tags


class TestModels:
    """Test data models."""

    def test_document_model(self, db_session: Session, temp_storage_path: Path):
        """Test Document ORM model."""
        doc = Document(
            name="test_doc",
            state="ok",
            version=1,
            chunk_hash="abc123",
            chunk_size=100,
            meta={"key": "value"},
        )
        db_session.add(doc)
        db_session.commit()

        # Retrieve
        retrieved = db_session.query(Document).filter_by(name="test_doc").first()
        assert retrieved is not None
        assert retrieved.name == "test_doc"
        assert retrieved.state == "ok"
        assert retrieved.version == 1
        assert retrieved.chunk_hash == "abc123"
        assert retrieved.chunk_size == 100
        assert retrieved.meta == {"key": "value"}
        assert isinstance(retrieved.ctime, datetime)
        assert isinstance(retrieved.mtime, datetime)
        assert isinstance(retrieved.atime, datetime)

    def test_dataset_model(self, db_session: Session):
        """Test Dataset ORM model."""
        dataset = Dataset(
            name="test_dataset",
            description={"app": "test"},
        )
        db_session.add(dataset)
        db_session.commit()

        retrieved = db_session.query(Dataset).filter_by(name="test_dataset").first()
        assert retrieved is not None
        assert retrieved.name == "test_dataset"
        assert retrieved.description == {"app": "test"}
        assert isinstance(retrieved.ctime, datetime)

    def test_array_model(self, db_session: Session, temp_storage_path: Path):
        """Test Array ORM model."""
        # First create a dataset
        dataset = Dataset(name="test_dataset")
        db_session.add(dataset)
        db_session.commit()

        # Create array
        array = Array(
            dataset_id=dataset.id,
            name="test_array",
            file_path="arrays/test.npy",
            inner_shape=[10],
            lu=[0],
            rd=[9],
        )
        db_session.add(array)
        db_session.commit()

        retrieved = db_session.query(Array).filter_by(name="test_array").first()
        assert retrieved is not None
        assert retrieved.dataset_id == dataset.id
        assert retrieved.name == "test_array"
        assert retrieved.inner_shape == [10]
        assert retrieved.lu == [0]
        assert retrieved.rd == [9]

        # Test relationship
        assert retrieved.dataset.name == "test_dataset"

    def test_config_model(self, db_session: Session):
        """Test Config ORM model with content addressing and reference counting."""
        config = Config(
            config_hash="abc123def456",
            size=1024,
            ref_count=0,
        )
        db_session.add(config)
        db_session.commit()

        retrieved = db_session.query(Config).filter_by(config_hash="abc123def456").first()
        assert retrieved is not None
        assert retrieved.config_hash == "abc123def456"
        assert retrieved.size == 1024
        assert retrieved.ref_count == 0
        assert isinstance(retrieved.ctime, datetime)
        assert isinstance(retrieved.atime, datetime)

    def test_script_model(self, db_session: Session):
        """Test Script ORM model with content addressing and reference counting."""
        script = Script(
            script_hash="xyz789abc123",
            size=2048,
            language="python",
            ref_count=1,
        )
        db_session.add(script)
        db_session.commit()

        retrieved = db_session.query(Script).filter_by(script_hash="xyz789abc123").first()
        assert retrieved is not None
        assert retrieved.script_hash == "xyz789abc123"
        assert retrieved.size == 2048
        assert retrieved.language == "python"
        assert retrieved.ref_count == 1

    def test_tag_model(self, db_session: Session):
        """Test Tag ORM model."""
        tag1 = Tag(name="test_tag")
        tag2 = Tag(name="another_tag")
        db_session.add_all([tag1, tag2])
        db_session.commit()

        retrieved = db_session.query(Tag).filter_by(name="test_tag").first()
        assert retrieved is not None
        assert retrieved.name == "test_tag"

    def test_document_tags(self, db_session: Session, temp_storage_path: Path):
        """Test document tags association."""
        # Create tags
        tag1 = get_or_create_tag(db_session, "tag1")
        tag2 = get_or_create_tag(db_session, "tag2")

        # Create document with tags
        doc = Document(
            name="tagged_doc",
            state="ok",
            chunk_hash="hash123",
            chunk_size=100,
        )
        doc.tags.append(tag1)
        doc.tags.append(tag2)
        db_session.add(doc)
        db_session.commit()

        # Retrieve and check tags
        retrieved = db_session.query(Document).filter_by(name="tagged_doc").first()
        assert len(retrieved.tags) == 2
        tag_names = [t.name for t in retrieved.tags]
        assert "tag1" in tag_names
        assert "tag2" in tag_names

    def test_dataset_tags(self, db_session: Session):
        """Test dataset tags association."""
        # Create tags
        tag1 = get_or_create_tag(db_session, "dataset_tag")

        # Create dataset with tags
        dataset = Dataset(
            name="tagged_dataset",
            description={"app": "test"},
        )
        dataset.tags.append(tag1)
        db_session.add(dataset)
        db_session.commit()

        # Retrieve and check tags
        retrieved = db_session.query(Dataset).filter_by(name="tagged_dataset").first()
        assert len(retrieved.tags) == 1
        assert retrieved.tags[0].name == "dataset_tag"

    def test_document_datasets(self, db_session: Session, temp_storage_path: Path):
        """Test document-dataset many-to-many relationship."""
        # Create dataset
        dataset = Dataset(name="source_dataset")
        db_session.add(dataset)
        db_session.commit()

        # Create document linked to dataset
        doc = Document(
            name="derived_doc",
            state="ok",
            chunk_hash="hash456",
            chunk_size=100,
        )
        doc.datasets.append(dataset)
        db_session.add(doc)
        db_session.commit()

        # Retrieve and check relationship from both sides
        retrieved_doc = db_session.query(Document).filter_by(name="derived_doc").first()
        assert len(retrieved_doc.datasets) == 1
        assert retrieved_doc.datasets[0].name == "source_dataset"

        retrieved_dataset = db_session.query(Dataset).filter_by(name="source_dataset").first()
        assert len(retrieved_dataset.documents) == 1
        assert retrieved_dataset.documents[0].name == "derived_doc"

    def test_query_documents(self, db_session: Session, temp_storage_path: Path):
        """Test query_documents function."""
        from qulab.storage.models.document import query_documents

        # Create documents
        doc1 = Document(name="doc1", state="ok", chunk_hash="h1", chunk_size=10)
        doc2 = Document(name="doc2", state="error", chunk_hash="h2", chunk_size=20)
        doc3 = Document(name="doc3", state="ok", chunk_hash="h3", chunk_size=30)
        db_session.add_all([doc1, doc2, doc3])
        db_session.commit()

        # Query all
        all_docs = query_documents(db_session)
        assert len(all_docs) == 3

        # Query by name
        docs_by_name = query_documents(db_session, name="doc1")
        assert len(docs_by_name) == 1
        assert docs_by_name[0].name == "doc1"

        # Query by state
        ok_docs = query_documents(db_session, state="ok")
        assert len(ok_docs) == 2

        # Query with limit
        limited = query_documents(db_session, limit=2)
        assert len(limited) == 2

    def test_count_documents(self, db_session: Session, temp_storage_path: Path):
        """Test count_documents function."""
        from qulab.storage.models.document import count_documents

        # Create documents
        doc1 = Document(name="doc1", state="ok", chunk_hash="h1", chunk_size=10)
        doc2 = Document(name="doc2", state="error", chunk_hash="h2", chunk_size=20)
        db_session.add_all([doc1, doc2])
        db_session.commit()

        # Count all
        assert count_documents(db_session) == 2

        # Count by state
        assert count_documents(db_session, state="ok") == 1
        assert count_documents(db_session, state="error") == 1
        assert count_documents(db_session, state="unknown") == 0

    def test_get_latest_document(self, db_session: Session, temp_storage_path: Path):
        """Test get_latest_document function."""
        from qulab.storage.models.document import get_latest_document

        # Create documents with the same name at different times
        doc1 = Document(name="test_doc", state="ok", chunk_hash="h1", chunk_size=10)
        db_session.add(doc1)
        db_session.commit()

        doc2 = Document(name="test_doc", state="ok", chunk_hash="h2", chunk_size=20)
        db_session.add(doc2)
        db_session.commit()

        doc3 = Document(name="test_doc", state="error", chunk_hash="h3", chunk_size=30)
        db_session.add(doc3)
        db_session.commit()

        # Get latest without state filter
        latest = get_latest_document(db_session, name="test_doc")
        assert latest is not None
        assert latest.name == "test_doc"
        assert latest.chunk_hash == "h3"  # Most recent

        # Get latest with state filter
        latest_ok = get_latest_document(db_session, name="test_doc", state="ok")
        assert latest_ok is not None
        assert latest_ok.state == "ok"
        assert latest_ok.chunk_hash == "h2"  # Most recent with state="ok"

        # Get latest for non-existent name
        not_found = get_latest_document(db_session, name="nonexistent")
        assert not_found is None

        # Get latest with state filter that matches nothing
        not_found_state = get_latest_document(db_session, name="test_doc", state="unknown")
        assert not_found_state is None

    def test_query_datasets(self, db_session: Session):
        """Test query_datasets function."""
        from qulab.storage.models.dataset import query_datasets

        # Create datasets
        ds1 = Dataset(name="ds1")
        ds2 = Dataset(name="ds2")
        db_session.add_all([ds1, ds2])
        db_session.commit()

        # Query all
        all_ds = query_datasets(db_session)
        assert len(all_ds) == 2

        # Query by name
        ds_by_name = query_datasets(db_session, name="ds1")
        assert len(ds_by_name) == 1

    def test_count_datasets(self, db_session: Session):
        """Test count_datasets function."""
        from qulab.storage.models.dataset import count_datasets

        # Create datasets
        ds1 = Dataset(name="ds1")
        ds2 = Dataset(name="ds2")
        db_session.add_all([ds1, ds2])
        db_session.commit()

        assert count_datasets(db_session) == 2

    def test_get_or_create_config(self, db_session: Session, temp_storage_path: Path, sample_config: dict):
        """Test get_or_create_config function."""
        config_obj1 = get_or_create_config(db_session, sample_config, temp_storage_path)
        config_obj2 = get_or_create_config(db_session, sample_config, temp_storage_path)

        # Should return same object
        assert config_obj1.id == config_obj2.id

        # Should have correct hash
        expected_hash = compute_config_hash(sample_config)
        assert config_obj1.config_hash == expected_hash

    def test_get_or_create_script(self, db_session: Session, temp_storage_path: Path, sample_script: str):
        """Test get_or_create_script function."""
        script_obj1 = get_or_create_script(db_session, sample_script, temp_storage_path)
        script_obj2 = get_or_create_script(db_session, sample_script, temp_storage_path)

        # Should return same object
        assert script_obj1.id == script_obj2.id

        # Should have correct hash
        expected_hash = compute_script_hash(sample_script)
        assert script_obj1.script_hash == expected_hash

    def test_config_ref_count(self, db_session: Session, temp_storage_path: Path):
        """Test config reference counting."""
        config_dict = {"test": "value"}
        config = get_or_create_config(db_session, config_dict, temp_storage_path)
        db_session.commit()  # Commit to persist the config
        initial_ref = config.ref_count

        # Increment
        increment_config_ref(db_session, config.id)
        db_session.commit()  # Commit the increment
        db_session.refresh(config)
        assert config.ref_count == initial_ref + 1

        # Decrement
        decrement_config_ref(db_session, config.id)
        db_session.commit()  # Commit the decrement
        db_session.refresh(config)
        assert config.ref_count == initial_ref

    def test_script_ref_count(self, db_session: Session, temp_storage_path: Path, sample_script: str):
        """Test script reference counting."""
        script = get_or_create_script(db_session, sample_script, temp_storage_path)
        db_session.commit()  # Commit to persist the script
        initial_ref = script.ref_count

        # Increment
        increment_script_ref(db_session, script.id)
        db_session.commit()  # Commit the increment
        db_session.refresh(script)
        assert script.ref_count == initial_ref + 1

        # Decrement
        decrement_script_ref(db_session, script.id)
        db_session.commit()  # Commit the decrement
        db_session.refresh(script)
        assert script.ref_count == initial_ref

    def test_compute_config_hash(self, sample_config: dict):
        """Test config hash computation."""
        hash1 = compute_config_hash(sample_config)
        hash2 = compute_config_hash(sample_config)

        # Same config should give same hash
        assert hash1 == hash2
        assert len(hash1) == 40  # SHA1 hex

        # Different config should give different hash
        different_config = {**sample_config, "extra": "key"}
        hash3 = compute_config_hash(different_config)
        assert hash3 != hash1

    def test_compute_script_hash(self, sample_script: str):
        """Test script hash computation."""
        hash1 = compute_script_hash(sample_script)
        hash2 = compute_script_hash(sample_script)

        # Same script should give same hash
        assert hash1 == hash2
        assert len(hash1) == 40  # SHA1 hex

        # Different script should give different hash
        different_script = sample_script + "\n# Extra comment"
        hash3 = compute_script_hash(different_script)
        assert hash3 != hash1

    def test_save_load_config(self, temp_storage_path: Path, sample_config: dict):
        """Test save and load config."""
        config_hash, size = save_config(sample_config, temp_storage_path)

        # Verify hash
        expected_hash = compute_config_hash(sample_config)
        assert config_hash == expected_hash

        # Load config
        loaded = load_config(config_hash, temp_storage_path)
        assert loaded == sample_config

    def test_save_load_script(self, temp_storage_path: Path, sample_script: str):
        """Test save and load script."""
        script_hash, size = save_script(sample_script, temp_storage_path)

        # Verify hash
        expected_hash = compute_script_hash(sample_script)
        assert script_hash == expected_hash

        # Load script
        loaded = load_script(script_hash, temp_storage_path)
        assert loaded == sample_script

    def test_get_object_with_tags(self, db_session: Session, temp_storage_path: Path):
        """Test get_object_with_tags function."""
        # Create tags
        tag1 = get_or_create_tag(db_session, "important")
        tag2 = get_or_create_tag(db_session, "draft")

        # Create documents with different tags
        doc1 = Document(name="doc1", state="ok", chunk_hash="h1", chunk_size=10)
        doc1.tags.append(tag1)

        doc2 = Document(name="doc2", state="ok", chunk_hash="h2", chunk_size=10)
        doc2.tags.append(tag2)

        doc3 = Document(name="doc3", state="ok", chunk_hash="h3", chunk_size=10)
        doc3.tags.extend([tag1, tag2])

        db_session.add_all([doc1, doc2, doc3])
        db_session.commit()

        # Query by single tag
        important_docs = get_object_with_tags(db_session, Document, "important").all()
        assert len(important_docs) == 2

        # Query by another tag
        draft_docs = get_object_with_tags(db_session, Document, "draft").all()
        assert len(draft_docs) == 2

    def test_document_version_chain(self, db_session: Session, temp_storage_path: Path):
        """Test document parent-child version chain."""
        # Create parent document
        parent = Document(name="doc", state="ok", chunk_hash="h1", chunk_size=10, version=1)
        db_session.add(parent)
        db_session.commit()

        # Create child document
        child = Document(
            name="doc",
            state="ok",
            chunk_hash="h2",
            chunk_size=20,
            version=2,
            parent_id=parent.id,
        )
        db_session.add(child)
        db_session.commit()

        # Check parent relationship
        retrieved_child = db_session.query(Document).filter_by(version=2).first()
        assert retrieved_child.parent_id == parent.id
        assert retrieved_child.parent.id == parent.id
        assert retrieved_child.parent.version == 1

        # Check children relationship
        retrieved_parent = db_session.query(Document).filter_by(version=1).first()
        assert len(retrieved_parent.children) == 1
        assert retrieved_parent.children[0].version == 2

    def test_config_deduplication(self, db_session: Session, temp_storage_path: Path):
        """Test that identical configs are deduplicated."""
        config_dict = {"key": "value", "nested": {"a": 1, "b": 2}}

        # Create same config multiple times
        config1 = get_or_create_config(db_session, config_dict, temp_storage_path)
        config2 = get_or_create_config(db_session, config_dict, temp_storage_path)
        config3 = get_or_create_config(db_session, config_dict, temp_storage_path)

        # Should all be the same object
        assert config1.id == config2.id == config3.id

        # Should only have one config in DB
        all_configs = db_session.query(Config).all()
        assert len(all_configs) == 1

    def test_script_deduplication(self, db_session: Session, temp_storage_path: Path, sample_script: str):
        """Test that identical scripts are deduplicated."""
        # Create same script multiple times
        script1 = get_or_create_script(db_session, sample_script, temp_storage_path)
        script2 = get_or_create_script(db_session, sample_script, temp_storage_path)
        script3 = get_or_create_script(db_session, sample_script, temp_storage_path)

        # Should all be the same object
        assert script1.id == script2.id == script3.id

        # Should only have one script in DB
        all_scripts = db_session.query(Script).all()
        assert len(all_scripts) == 1
