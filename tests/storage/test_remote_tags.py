"""Tests for RemoteStorage tag editing functionality."""

import asyncio
import os
import socket
import tempfile
import threading
import time
from pathlib import Path

import pytest
import zmq

# Skip these tests if RUN_REMOTE_TESTS is not set (due to ZMQ port binding issues in concurrent test runs)
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_REMOTE_TESTS") != "1",
    reason="Remote tests skipped by default. Set RUN_REMOTE_TESTS=1 to run."
)

from qulab.storage.local import LocalStorage
from qulab.storage.remote import RemoteStorage
from qulab.storage.server import StorageServer
from qulab.sys.rpc.zmq_socket import ZMQContextManager


class ServerRunner:
    """Helper class to run storage server in background."""

    _lock = threading.Lock()
    _base_port = 35000
    _port_counter = 0

    def __init__(self, storage: LocalStorage, port: int):
        self.storage = storage
        self.port = port
        self._running = False
        self._thread = None
        self._loop = None

    @classmethod
    def get_free_port(cls):
        """Get a unique port using sequential allocation with locking."""
        with cls._lock:
            cls._port_counter += 1
            return cls._base_port + cls._port_counter

    def start(self):
        """Start the server in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        # Wait for server to be ready
        time.sleep(0.2)

    def stop(self):
        """Stop the server."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)

    def _run(self):
        """Server main loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        finally:
            self._loop.close()

    async def _serve(self):
        """Serve requests."""
        server = StorageServer(self.storage, host="127.0.0.1", port=self.port)

        async with ZMQContextManager(zmq.ROUTER, bind=f"tcp://127.0.0.1:{self.port}") as sock:
            while self._running:
                try:
                    identity, msg = await asyncio.wait_for(
                        sock.recv_multipart(), timeout=0.05
                    )
                    import pickle
                    message = pickle.loads(msg)
                    response = await server.handle(message)
                    await sock.send_multipart(
                        [identity, pickle.dumps(response)]
                    )
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    continue


@pytest.fixture(scope="function")
def remote_storage():
    """Create a RemoteStorage connected to a test server."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(base_path=tmpdir)
        port = ServerRunner.get_free_port()

        runner = ServerRunner(storage, port)
        runner.start()

        # Add small delay to ensure server is fully ready
        time.sleep(0.1)

        try:
            remote = RemoteStorage(f"tcp://127.0.0.1:{port}", timeout=10.0)
            yield remote
        finally:
            runner.stop()


class TestRemoteDocumentTags:
    """Test RemoteStorage document tag editing functionality."""

    def test_create_document_with_tags(self, remote_storage):
        """Test creating a document with tags via remote storage."""
        doc_ref = remote_storage.create_document(
            name="remote_doc",
            data={"key": "value"},
            state="ok",
            tags=["tag1", "tag2"],
        )

        assert doc_ref.id is not None

        # Verify tags via remote get
        doc = remote_storage.get_document(doc_ref.id)
        assert "tag1" in doc.tags
        assert "tag2" in doc.tags

    def test_remote_document_add_tags(self, remote_storage):
        """Test adding tags to a document via RemoteStorage."""
        # Create document with initial tags
        doc_ref = remote_storage.create_document(
            name="remote_doc",
            data={"key": "value"},
            tags=["initial"],
        )

        # Add tags via storage API
        remote_storage.document_add_tags(doc_ref.id, ["tag1", "tag2"])

        # Verify tags
        doc = remote_storage.get_document(doc_ref.id)
        assert "initial" in doc.tags
        assert "tag1" in doc.tags
        assert "tag2" in doc.tags

    def test_remote_document_remove_tags(self, remote_storage):
        """Test removing tags from a document via RemoteStorage."""
        # Create document with tags
        doc_ref = remote_storage.create_document(
            name="remote_doc",
            data={"key": "value"},
            tags=["tag1", "tag2", "tag3"],
        )

        # Remove tags via storage API
        remote_storage.document_remove_tags(doc_ref.id, ["tag2"])

        # Verify tags
        doc = remote_storage.get_document(doc_ref.id)
        assert "tag1" in doc.tags
        assert "tag2" not in doc.tags
        assert "tag3" in doc.tags

    def test_remote_document_set_tags(self, remote_storage):
        """Test setting tags for a document via RemoteStorage."""
        # Create document with initial tags
        doc_ref = remote_storage.create_document(
            name="remote_doc",
            data={"key": "value"},
            tags=["old1", "old2"],
        )

        # Set tags via storage API
        remote_storage.document_set_tags(doc_ref.id, ["new1", "new2"])

        # Verify tags
        doc = remote_storage.get_document(doc_ref.id)
        assert set(doc.tags) == {"new1", "new2"}

    def test_remote_document_add_tag_method(self, remote_storage):
        """Test RemoteDocument.add_tag() method."""
        doc_ref = remote_storage.create_document(
            name="remote_doc",
            data={"key": "value"},
            tags=["initial"],
        )

        doc = remote_storage.get_document(doc_ref.id)
        doc.add_tag("new_tag")

        # Verify tag was added
        assert "new_tag" in doc.tags

        # Reload and verify
        reloaded = remote_storage.get_document(doc_ref.id)
        assert "new_tag" in reloaded.tags

    def test_remote_document_remove_tag_method(self, remote_storage):
        """Test RemoteDocument.remove_tag() method."""
        doc_ref = remote_storage.create_document(
            name="remote_doc",
            data={"key": "value"},
            tags=["tag1", "tag2"],
        )

        doc = remote_storage.get_document(doc_ref.id)
        doc.remove_tag("tag1")

        # Verify tag was removed
        assert "tag1" not in doc.tags
        assert "tag2" in doc.tags

    def test_remote_document_set_tags_method(self, remote_storage):
        """Test RemoteDocument.set_tags() method."""
        doc_ref = remote_storage.create_document(
            name="remote_doc",
            data={"key": "value"},
            tags=["old1", "old2"],
        )

        doc = remote_storage.get_document(doc_ref.id)
        doc.set_tags(["new1", "new2", "new3"])

        # Verify tags
        assert set(doc.tags) == {"new1", "new2", "new3"}

    def test_remote_query_documents_by_tags(self, remote_storage):
        """Test querying documents by tags via RemoteStorage."""
        # Create documents with different tags
        doc1 = remote_storage.create_document(
            name="doc1",
            data={"id": 1},
            tags=["searchable", "tag1"],
        )
        doc2 = remote_storage.create_document(
            name="doc2",
            data={"id": 2},
            tags=["searchable", "tag2"],
        )
        remote_storage.create_document(
            name="doc3",
            data={"id": 3},
            tags=["other"],
        )

        # Query by tag
        results = list(remote_storage.query_documents(tags=["searchable"]))
        assert len(results) == 2
        result_ids = {r.id for r in results}
        assert doc1.id in result_ids
        assert doc2.id in result_ids


class TestRemoteDatasetTags:
    """Test RemoteStorage dataset tag editing functionality."""

    def test_create_dataset_with_tags(self, remote_storage):
        """Test creating a dataset with tags via remote storage."""
        ds_ref = remote_storage.create_dataset(
            name="remote_dataset",
            description={"app": "test"},
            tags=["tag1", "tag2"],
        )

        assert ds_ref.id is not None

        # Verify tags via remote get
        ds = remote_storage.get_dataset(ds_ref.id)
        assert "tag1" in ds.tags
        assert "tag2" in ds.tags

    def test_remote_dataset_add_tags(self, remote_storage):
        """Test adding tags to a dataset via RemoteStorage."""
        # Create dataset with initial tags
        ds_ref = remote_storage.create_dataset(
            name="remote_dataset",
            description={},
            tags=["initial"],
        )

        # Add tags via storage API
        remote_storage.dataset_add_tags(ds_ref.id, ["tag1", "tag2"])

        # Verify tags
        ds = remote_storage.get_dataset(ds_ref.id)
        assert "initial" in ds.tags
        assert "tag1" in ds.tags
        assert "tag2" in ds.tags

    def test_remote_dataset_remove_tags(self, remote_storage):
        """Test removing tags from a dataset via RemoteStorage."""
        # Create dataset with tags
        ds_ref = remote_storage.create_dataset(
            name="remote_dataset",
            description={},
            tags=["tag1", "tag2", "tag3"],
        )

        # Remove tags via storage API
        remote_storage.dataset_remove_tags(ds_ref.id, ["tag2"])

        # Verify tags
        ds = remote_storage.get_dataset(ds_ref.id)
        assert "tag1" in ds.tags
        assert "tag2" not in ds.tags
        assert "tag3" in ds.tags

    def test_remote_dataset_set_tags(self, remote_storage):
        """Test setting tags for a dataset via RemoteStorage."""
        # Create dataset with initial tags
        ds_ref = remote_storage.create_dataset(
            name="remote_dataset",
            description={},
            tags=["old1", "old2"],
        )

        # Set tags via storage API
        remote_storage.dataset_set_tags(ds_ref.id, ["new1", "new2"])

        # Verify tags
        ds = remote_storage.get_dataset(ds_ref.id)
        assert set(ds.tags) == {"new1", "new2"}

    def test_remote_dataset_add_tag_method(self, remote_storage):
        """Test RemoteDataset.add_tag() method."""
        ds_ref = remote_storage.create_dataset(
            name="remote_dataset",
            description={},
            tags=["initial"],
        )

        ds = remote_storage.get_dataset(ds_ref.id)
        ds.add_tag("new_tag")

        # Verify tag was added
        assert "new_tag" in ds.tags

        # Reload and verify
        reloaded = remote_storage.get_dataset(ds_ref.id)
        assert "new_tag" in reloaded.tags

    def test_remote_dataset_remove_tag_method(self, remote_storage):
        """Test RemoteDataset.remove_tag() method."""
        ds_ref = remote_storage.create_dataset(
            name="remote_dataset",
            description={},
            tags=["tag1", "tag2"],
        )

        ds = remote_storage.get_dataset(ds_ref.id)
        ds.remove_tag("tag1")

        # Verify tag was removed
        assert "tag1" not in ds.tags
        assert "tag2" in ds.tags

    def test_remote_dataset_set_tags_method(self, remote_storage):
        """Test RemoteDataset.set_tags() method."""
        ds_ref = remote_storage.create_dataset(
            name="remote_dataset",
            description={},
            tags=["old1", "old2"],
        )

        ds = remote_storage.get_dataset(ds_ref.id)
        ds.set_tags(["new1", "new2", "new3"])

        # Verify tags
        assert set(ds.tags) == {"new1", "new2", "new3"}

    def test_remote_query_datasets_by_tags(self, remote_storage):
        """Test querying datasets by tags via RemoteStorage."""
        # Create datasets with different tags
        ds1 = remote_storage.create_dataset(
            name="ds1",
            description={"id": 1},
            tags=["searchable", "tag1"],
        )
        ds2 = remote_storage.create_dataset(
            name="ds2",
            description={"id": 2},
            tags=["searchable", "tag2"],
        )
        remote_storage.create_dataset(
            name="ds3",
            description={"id": 3},
            tags=["other"],
        )

        # Query by tag
        results = list(remote_storage.query_datasets(tags=["searchable"]))
        assert len(results) == 2
        result_ids = {r.id for r in results}
        assert ds1.id in result_ids
        assert ds2.id in result_ids
