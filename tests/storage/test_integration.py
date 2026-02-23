"""Integration tests for storage module."""

import numpy as np
import pytest

from qulab.storage.local import LocalStorage
from qulab.storage.document import Document
from qulab.storage.dataset import Dataset
from qulab.storage.models.config import Config
from qulab.storage.models.script import Script


class TestIntegration:
    """Integration tests for the storage system."""

    def test_full_document_workflow(self, local_storage: LocalStorage):
        """Test complete document workflow: create, query, get, delete."""
        # Create documents
        ref1 = local_storage.create_document(
            name="workflow_doc",
            data={"stage": 1, "results": [1, 2, 3]},
            state="ok",
            tags=["workflow", "test"],
        )

        ref2 = local_storage.create_document(
            name="workflow_doc",
            data={"stage": 2, "results": [4, 5, 6]},
            state="error",
            tags=["workflow", "production"],
            parent_id=ref1.id,
        )

        # Query documents
        all_docs = list(local_storage.query_documents())
        assert len(all_docs) == 2

        # Query by tags
        workflow_docs = list(local_storage.query_documents(tags=["workflow"]))
        assert len(workflow_docs) == 2

        # Query by state
        ok_docs = list(local_storage.query_documents(state="ok"))
        assert len(ok_docs) == 1

        # Get and verify
        doc1 = local_storage.get_document(ref1.id)
        assert doc1.data["stage"] == 1
        assert doc1.state == "ok"

        doc2 = local_storage.get_document(ref2.id)
        assert doc2.data["stage"] == 2
        assert doc2.parent_id == ref1.id

        # Delete
        assert ref1.delete() is True

        # Verify deletion
        with pytest.raises(KeyError):
            local_storage.get_document(ref1.id)

    def test_full_dataset_workflow(self, local_storage: LocalStorage):
        """Test complete dataset workflow: create, append data, query, get, delete."""
        # Create dataset
        ref = local_storage.create_dataset(
            name="workflow_dataset",
            description={"app": "test", "scan_type": "1D"},
        )

        # Get dataset and append data
        dataset = ref.get()

        # Append data points
        for i in range(10):
            dataset.append(
                (i, 0),
                {"x": float(i), "y": float(i ** 2), "amplitude": np.random.rand()}
            )

        # Flush to disk
        dataset.flush()

        # Verify arrays
        assert "x" in dataset.keys()
        assert "y" in dataset.keys()
        assert "amplitude" in dataset.keys()

        # Query datasets
        all_ds = list(local_storage.query_datasets())
        assert len(all_ds) == 1

        # Get dataset
        retrieved = local_storage.get_dataset(ref.id)
        assert retrieved.name == "workflow_dataset"

        # Verify data
        x_array = retrieved.get_array("x")
        assert len(list(x_array.iter())) == 10

        # Delete
        assert ref.delete() is True

        # Verify deletion
        with pytest.raises(KeyError):
            local_storage.get_dataset(ref.id)

    def test_config_deduplication(self, local_storage: LocalStorage, sample_config: dict):
        """Test that identical configs are stored only once."""
        from qulab.storage.models.config import get_or_create_config
        from qulab.storage.models.base import SessionManager

        # Create multiple datasets with same config
        ref1 = local_storage.create_dataset(
            name="ds1",
            description={},
            config=sample_config,
        )

        ref2 = local_storage.create_dataset(
            name="ds2",
            description={},
            config=sample_config,
        )

        ref3 = local_storage.create_dataset(
            name="ds3",
            description={},
            config=sample_config,
        )

        # Verify all datasets have same config hash
        ds1 = ref1.get()
        ds2 = ref2.get()
        ds3 = ref3.get()

        assert ds1.config_hash == ds2.config_hash == ds3.config_hash

        # Verify only one config in database
        with local_storage._get_session() as session:
            config_count = session.query(Config).count()

            # Should have only 1 config (all datasets share it)
            # But note: configs might be created independently in other tests
            # So we just verify the deduplication for this specific hash
            config_hash = ds1.config_hash
            matching_configs = session.query(Config).filter_by(config_hash=config_hash).count()
            assert matching_configs == 1

    def test_script_deduplication(self, local_storage: LocalStorage, sample_script: str):
        """Test that identical scripts are stored only once."""
        # Create multiple documents with same script
        ref1 = local_storage.create_document(
            name="doc1",
            data={},
            script=sample_script,
        )

        ref2 = local_storage.create_document(
            name="doc2",
            data={},
            script=sample_script,
        )

        # Verify both documents have same script hash
        doc1 = ref1.get()
        doc2 = ref2.get()

        assert doc1.script_hash == doc2.script_hash

        # Verify only one script in database
        with local_storage._get_session() as session:
            script_hash = doc1.script_hash
            matching_scripts = session.query(Script).filter_by(script_hash=script_hash).count()
            assert matching_scripts == 1

    def test_document_with_datasets(self, local_storage: LocalStorage):
        """Test document-dataset association workflow."""
        # Create datasets
        ds_refs = []
        for i in range(3):
            ref = local_storage.create_dataset(
                name=f"source_data_{i}",
                description={"index": i},
            )
            ds_refs.append(ref)

        datasets = [ref.get() for ref in ds_refs]

        # Create analysis document linked to all datasets (pass IDs, not objects)
        analysis_ref = local_storage.create_document(
            name="analysis_report",
            data={
                "fit_results": {"amplitude": 1.0, "frequency": 5.2e9},
                "quality_factor": 15000,
            },
            state="ok",
            tags=["analysis", "qubit"],
            datasets=[ds.id for ds in datasets],
        )

        # Verify associations
        analysis_doc = analysis_ref.get()
        associated_datasets = analysis_doc.get_datasets(local_storage)
        assert len(associated_datasets) == 3

        # Verify from dataset side
        for ds in associated_datasets:
            related_docs = ds.get_documents()
            assert len(related_docs) == 1
            assert related_docs[0].name == "analysis_report"

    def test_version_chain(self, local_storage: LocalStorage):
        """Test document version chain."""
        # Create initial document
        v1_ref = local_storage.create_document(
            name="versioned_analysis",
            data={"version": "1.0", "content": "Initial analysis"},
            state="ok",
        )

        # Create new versions
        current_ref = v1_ref
        for i in range(2, 6):  # versions 2-5
            current_doc = current_ref.get()
            current_doc.data["version"] = f"{i}.0"
            current_doc.data["content"] = f"Update {i-1}"
            current_ref = current_doc.save(local_storage)

        # Verify version chain
        final_doc = current_ref.get()
        assert final_doc.version == 5

        # Walk back through versions
        versions = []
        doc = final_doc
        while doc:
            versions.append(doc.version)
            if doc.parent_id:
                doc = local_storage.get_document(doc.parent_id)
            else:
                break

        assert versions == [5, 4, 3, 2, 1]

    def test_complex_array_operations(self, local_storage: LocalStorage):
        """Test complex array operations."""
        # Create dataset
        ref = local_storage.create_dataset(name="complex_array_test", description={})
        dataset = ref.get()

        # Create array with complex inner shape
        array = dataset.create_array("complex_data", (2, 3))

        # Append data with complex structure
        for i in range(5):
            for j in range(5):
                # Each point has a 2x3 matrix
                matrix = [[i*5+j+k*3+l for l in range(3)] for k in range(2)]
                array.append((i, j), matrix)

        # Flush
        array.flush()

        # Test iteration
        items = list(array.iter())
        assert len(items) == 25

        # Test positions and values
        positions = array.positions()
        values = array.value()
        assert len(positions) == 25
        assert len(values) == 25

        # Test numpy array conversion
        np_array = array.toarray()
        assert np_array.shape == (5, 5, 2, 3)

        # Test slicing
        slice_data = array[0:2, 0:2]
        assert slice_data.shape == (2, 2, 2, 3)

        # Test single element
        element = array[2, 3]
        assert element.shape == (2, 3)

    def test_empty_data_handling(self, local_storage: LocalStorage):
        """Test handling of empty data."""
        # Create empty document
        ref = local_storage.create_document(
            name="empty_doc",
            data={},
        )

        doc = ref.get()
        assert doc.data == {}

        # Create empty dataset
        ds_ref = local_storage.create_dataset(
            name="empty_dataset",
            description={},
        )

        dataset = ds_ref.get()
        assert dataset.keys() == []
        assert dataset.description == {}

    def test_unicode_and_special_chars(self, local_storage: LocalStorage):
        """Test handling of unicode and special characters."""
        # Document with unicode
        ref = local_storage.create_document(
            name="unicode_doc",
            data={
                "chinese": "测试中文",
                "emoji": "🎉🎊🎁",
                "math": "∫∂∆∑∏",
                "special": "<>&'\"",
            },
        )

        doc = ref.get()
        assert doc.data["chinese"] == "测试中文"
        assert doc.data["emoji"] == "🎉🎊🎁"

        # Dataset with unicode
        ds_ref = local_storage.create_dataset(
            name="unicode_dataset",
            description={"note": "测试备注"},
        )

        dataset = ds_ref.get()
        assert dataset.description["note"] == "测试备注"

    def test_large_number_of_documents(self, local_storage: LocalStorage):
        """Test handling of large number of documents."""
        # Create many documents
        refs = []
        for i in range(100):
            ref = local_storage.create_document(
                name=f"bulk_doc_{i}",
                data={"index": i},
                tags=["bulk", f"tag_{i % 10}"],
            )
            refs.append(ref)

        # Query all
        all_docs = list(local_storage.query_documents())
        assert len(all_docs) == 100

        # Query by tag
        tag_0_docs = list(local_storage.query_documents(tags=["tag_0"]))
        assert len(tag_0_docs) == 10

        # Count
        assert local_storage.count_documents() == 100

        # Delete some
        for ref in refs[:50]:
            ref.delete()

        assert local_storage.count_documents() == 50

    def test_dataset_with_config_and_script(self, local_storage: LocalStorage, sample_config: dict, sample_script: str):
        """Test dataset with both config and script."""
        # Note: LocalStorage.create_dataset doesn't support tags directly
        ref = local_storage.create_dataset(
            name="complete_dataset",
            description={"app": "integration_test"},
            config=sample_config,
            script=sample_script,
        )

        dataset = ref.get()

        # Verify config
        loaded_config = dataset.config
        assert loaded_config == sample_config

        # Verify script
        loaded_script = dataset.script
        assert loaded_script == sample_script

        # Verify hashes
        assert dataset.config_hash is not None
        assert dataset.script_hash is not None

    def test_multiple_arrays_in_dataset(self, local_storage: LocalStorage):
        """Test dataset with multiple arrays."""
        ref = local_storage.create_dataset(name="multi_array_dataset", description={})
        dataset = ref.get()

        # Create multiple arrays
        arrays = {}
        for name in ["i", "q", "phase", "amplitude"]:
            arrays[name] = dataset.create_array(name, (1,))

        # Append data to all arrays
        for i in range(100):
            dataset.append(
                (i,),
                {
                    "i": np.random.randn(),
                    "q": np.random.randn(),
                    "phase": np.random.rand() * 2 * np.pi,
                    "amplitude": np.random.rand(),
                }
            )

        # Flush
        dataset.flush()

        # Verify all arrays
        for name in ["i", "q", "phase", "amplitude"]:
            arr = dataset.get_array(name)
            items = list(arr.iter())
            assert len(items) == 100

    def test_document_save_preserves_relations(self, local_storage: LocalStorage):
        """Test that document save preserves dataset relations."""
        # Create dataset
        ds_ref = local_storage.create_dataset(name="related_dataset", description={})
        dataset = ds_ref.get()

        # Create document with dataset (pass ID, not object)
        doc_ref = local_storage.create_document(
            name="linked_doc",
            data={"v": 1},
            datasets=[dataset.id],
        )

        # Save new version
        doc = doc_ref.get()
        doc.data["v"] = 2
        new_ref = doc.save(local_storage)

        # Verify new version still has dataset
        new_doc = new_ref.get()
        associated = new_doc.get_datasets(local_storage)
        assert len(associated) == 1
        assert associated[0].name == "related_dataset"

    def test_query_by_multiple_tags(self, local_storage: LocalStorage):
        """Test querying with multiple tags."""
        # Create documents with different tag combinations
        local_storage.create_document(name="doc1", data={}, tags=["a", "b"])
        local_storage.create_document(name="doc2", data={}, tags=["b", "c"])
        local_storage.create_document(name="doc3", data={}, tags=["a", "c"])
        local_storage.create_document(name="doc4", data={}, tags=["a", "b", "c"])

        # Query by single tag
        a_docs = list(local_storage.query_documents(tags=["a"]))
        assert len(a_docs) == 3

        # Query by multiple tags (AND logic)
        # Note: Implementation may vary - this tests current behavior
        ab_docs = list(local_storage.query_documents(tags=["a", "b"]))
        # Should return docs with both tags
        assert len(ab_docs) == 2  # doc1 and doc4

    def test_concurrent_array_append(self, local_storage: LocalStorage):
        """Test array operations are thread-safe."""
        import threading

        ref = local_storage.create_dataset(name="concurrent_test", description={})
        dataset = ref.get()
        array = dataset.create_array("concurrent", (1,))

        results = []
        errors = []

        def append_data(thread_id, count):
            try:
                for i in range(count):
                    array.append((thread_id * 1000 + i,), [float(i)])
                results.append(thread_id)
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Run concurrent appends
        threads = []
        for i in range(5):
            t = threading.Thread(target=append_data, args=(i, 20))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Should have no errors
        assert len(errors) == 0
        assert len(results) == 5

        # Verify data
        array.flush()
        items = list(array.iter())
        assert len(items) == 100
