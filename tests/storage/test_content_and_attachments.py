"""Tests for Content fields and Attachment system."""

import pytest
from pathlib import Path

from qulab.storage import LocalStorage, ContentRenderer, Attachment
from qulab.storage.local import AttachmentRef


class TestContentField:
    """Test Content field functionality for Dataset and Document."""

    def test_dataset_create_with_content(self, local_storage: LocalStorage):
        """Test creating a dataset with content."""
        ds_ref = local_storage.create_dataset(
            name="test_dataset_content",
            description={"type": "test"},
            content="# Test Dataset\n\nThis is a test.",
            content_type="text/markdown",
        )

        ds = ds_ref.get()
        assert ds.content == "# Test Dataset\n\nThis is a test."
        assert ds.content_type == "text/markdown"
        assert ds.content_hash is not None

    def test_dataset_content_lazy_loading(self, local_storage: LocalStorage):
        """Test that content is lazy loaded."""
        ds_ref = local_storage.create_dataset(
            name="test_lazy_content",
            description={"type": "test"},
            content="Lazy loading test content",
        )

        # Load dataset without accessing content
        ds = local_storage.get_dataset(ds_ref.id)
        assert ds._content is None  # Not loaded yet

        # Access content triggers lazy loading
        content = ds.content
        assert content == "Lazy loading test content"
        assert ds._content is not None  # Now loaded

    def test_dataset_save_content(self, local_storage: LocalStorage):
        """Test saving content to an existing dataset."""
        ds_ref = local_storage.create_dataset(
            name="test_save_content",
            description={"type": "test"},
        )

        ds = ds_ref.get()
        assert ds.content is None

        # Save new content
        ds.save_content("# Updated Content\n\nNew content here.", "text/markdown")

        # Reload and verify
        ds2 = local_storage.get_dataset(ds_ref.id)
        assert ds2.content == "# Updated Content\n\nNew content here."
        assert ds2.content_type == "text/markdown"

    def test_dataset_content_default_type(self, local_storage: LocalStorage):
        """Test default content type is text/markdown."""
        ds_ref = local_storage.create_dataset(
            name="test_default_type",
            description={"type": "test"},
            content="Some content",
        )

        ds = ds_ref.get()
        assert ds.content_type == "text/markdown"

    def test_document_create_with_content(self, local_storage: LocalStorage):
        """Test creating a document with content."""
        doc_ref = local_storage.create_document(
            name="test_doc_content",
            data={"key": "value"},
            content="# Report\n\nResults: success",
            content_type="text/markdown",
        )

        doc = doc_ref.get()
        assert doc.content == "# Report\n\nResults: success"
        assert doc.content_type == "text/markdown"
        assert doc.content_hash is not None
        assert doc.data == {"key": "value"}  # data and content coexist

    def test_document_content_and_data_coexist(self, local_storage: LocalStorage):
        """Test that content and data fields can coexist."""
        doc_ref = local_storage.create_document(
            name="test_coexist",
            data={"results": [1, 2, 3], "fit_params": {"a": 1, "b": 2}},
            content="""
# Analysis Results

The fit parameters are shown in the data field.

## Summary

- Parameter a: 1
- Parameter b: 2
""",
        )

        doc = doc_ref.get()
        assert doc.data["results"] == [1, 2, 3]
        assert "fit_params" in doc.data
        assert "Analysis Results" in doc.content
        assert "Parameter a" in doc.content

    def test_document_to_dict_includes_content(self, local_storage: LocalStorage):
        """Test Document.to_dict() includes content fields."""
        doc_ref = local_storage.create_document(
            name="test_to_dict",
            data={"key": "value"},
            content="Test content",
            content_type="text/markdown",
        )

        doc = doc_ref.get()
        doc_dict = doc.to_dict()

        assert "content" in doc_dict
        assert "content_hash" in doc_dict
        assert "content_type" in doc_dict
        assert doc_dict["content"] == "Test content"
        assert doc_dict["content_type"] == "text/markdown"

    def test_document_from_dict_with_content(self, local_storage: LocalStorage):
        """Test Document.from_dict() restores content fields."""
        from qulab.storage.document import Document

        doc_dict = {
            "id": 1,
            "name": "test_from_dict",
            "data": {"key": "value"},
            "content": "Restored content",
            "content_hash": "abc123",
            "content_type": "text/plain",
            "meta": {},
            "ctime": "2024-01-01T00:00:00",
            "mtime": "2024-01-01T00:00:00",
            "atime": "2024-01-01T00:00:00",
            "tags": [],
            "state": "ok",
            "version": 1,
            "parent_id": None,
        }

        doc = Document.from_dict(doc_dict)
        assert doc.content == "Restored content"
        assert doc.content_hash == "abc123"
        assert doc.content_type == "text/plain"

    def test_dataset_to_dict_includes_content(self, local_storage: LocalStorage):
        """Test Dataset.to_dict() includes content fields."""
        ds_ref = local_storage.create_dataset(
            name="test_ds_to_dict",
            description={"type": "test"},
            content="Dataset content",
        )

        ds = ds_ref.get()
        ds_dict = ds.to_dict()

        assert "content" in ds_dict
        assert "content_hash" in ds_dict
        assert "content_type" in ds_dict
        assert ds_dict["content"] == "Dataset content"


class TestAttachment:
    """Test Attachment functionality."""

    def test_create_attachment_from_file(self, local_storage: LocalStorage, tmp_path: Path):
        """Test creating attachment from file."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        att_ref = local_storage.create_attachment(
            file_path=test_file,
            name="test.txt",
            mime_type="text/plain",
            meta={"author": "test"},
        )

        assert isinstance(att_ref, AttachmentRef)
        assert att_ref.id is not None
        assert att_ref.name == "test.txt"

        # Load and verify
        att = att_ref.get()
        assert att.name == "test.txt"
        assert att.mime_type == "text/plain"
        assert att.meta == {"author": "test"}
        assert att.read() == b"Hello, World!"

    def test_create_attachment_from_bytes(self, local_storage: LocalStorage):
        """Test creating attachment from bytes."""
        data = b"\x89PNG\r\n\x1a\n"  # Fake PNG header

        att_ref = local_storage.create_attachment_from_bytes(
            data=data,
            name="image.png",
            mime_type="image/png",
            meta={"width": 100, "height": 100},
        )

        att = att_ref.get()
        assert att.name == "image.png"
        assert att.mime_type == "image/png"
        assert att.size == len(data)
        assert att.read() == data

    def test_attachment_auto_mime_detection(self, local_storage: LocalStorage, tmp_path: Path):
        """Test automatic MIME type detection."""
        test_file = tmp_path / "image.png"
        test_file.write_bytes(b"fake_png_data")

        att_ref = local_storage.create_attachment(
            file_path=test_file,
        )

        att = att_ref.get()
        assert att.mime_type == "image/png"

    def test_attachment_deduplication(self, local_storage: LocalStorage):
        """Test that identical content is deduplicated."""
        data = b"Same content for deduplication test"

        att_ref1 = local_storage.create_attachment_from_bytes(
            data=data, name="file1.txt", mime_type="text/plain"
        )
        att_ref2 = local_storage.create_attachment_from_bytes(
            data=data, name="file2.txt", mime_type="text/plain"
        )

        # Both attachments should have the same chunk_hash
        att1 = att_ref1.get()
        att2 = att_ref2.get()
        assert att1._chunk_hash == att2._chunk_hash

    def test_attachment_save_to_file(self, local_storage: LocalStorage, tmp_path: Path):
        """Test saving attachment to file system."""
        data = b"Test data to save"
        att_ref = local_storage.create_attachment_from_bytes(
            data=data, name="test.dat", mime_type="application/octet-stream"
        )

        att = att_ref.get()
        output_path = tmp_path / "output.dat"
        att.save_to_file(output_path)

        assert output_path.read_bytes() == data

    def test_attachment_query(self, local_storage: LocalStorage):
        """Test querying attachments."""
        # Create several attachments
        local_storage.create_attachment_from_bytes(
            b"image1", name="img1.png", mime_type="image/png"
        )
        local_storage.create_attachment_from_bytes(
            b"image2", name="img2.png", mime_type="image/png"
        )
        local_storage.create_attachment_from_bytes(
            b"doc1", name="doc.pdf", mime_type="application/pdf"
        )

        # Query all
        all_atts = list(local_storage.query_attachments())
        assert len(all_atts) == 3

        # Query by name pattern
        png_atts = list(local_storage.query_attachments(name="img*"))
        assert len(png_atts) == 2

        # Query by mime type
        pdf_atts = list(local_storage.query_attachments(mime_type="application/pdf"))
        assert len(pdf_atts) == 1

    def test_attachment_count(self, local_storage: LocalStorage):
        """Test counting attachments."""
        local_storage.create_attachment_from_bytes(
            b"test", name="test.txt", mime_type="text/plain"
        )

        assert local_storage.count_attachments() == 1
        assert local_storage.count_attachments(mime_type="text/plain") == 1
        assert local_storage.count_attachments(mime_type="image/png") == 0

    def test_attachment_get_by_id(self, local_storage: LocalStorage):
        """Test getting attachment by ID."""
        att_ref = local_storage.create_attachment_from_bytes(
            b"test", name="test.txt", mime_type="text/plain"
        )

        att = local_storage.get_attachment(att_ref.id)
        assert att.name == "test.txt"
        assert att.read() == b"test"

    def test_attachment_not_found(self, local_storage: LocalStorage):
        """Test getting non-existent attachment raises KeyError."""
        with pytest.raises(KeyError):
            local_storage.get_attachment(99999)


class TestAttachmentRelationships:
    """Test many-to-many relationships between Attachments and Dataset/Document."""

    def test_dataset_add_attachment(self, local_storage: LocalStorage):
        """Test adding attachment to dataset."""
        ds_ref = local_storage.create_dataset(
            name="test_ds_attach", description={"type": "test"}
        )
        att_ref = local_storage.create_attachment_from_bytes(
            b"data", name="data.txt", mime_type="text/plain"
        )

        ds = ds_ref.get()
        ds.add_attachment(att_ref.id)

        # Verify attachment is associated
        attachments = ds.get_attachments()
        assert len(attachments) == 1
        assert attachments[0].id == att_ref.id

    def test_dataset_remove_attachment(self, local_storage: LocalStorage):
        """Test removing attachment from dataset."""
        ds_ref = local_storage.create_dataset(
            name="test_ds_remove", description={"type": "test"}
        )
        att_ref = local_storage.create_attachment_from_bytes(
            b"data", name="data.txt", mime_type="text/plain"
        )

        ds = ds_ref.get()
        ds.add_attachment(att_ref.id)
        ds.remove_attachment(att_ref.id)

        # Verify attachment is removed
        attachments = ds.get_attachments()
        assert len(attachments) == 0

    def test_document_add_attachment(self, local_storage: LocalStorage):
        """Test adding attachment to document."""
        doc_ref = local_storage.create_document(
            name="test_doc_attach", data={"key": "value"}
        )
        att_ref = local_storage.create_attachment_from_bytes(
            b"image", name="fig.png", mime_type="image/png"
        )

        doc = doc_ref.get()
        doc.add_attachment(att_ref.id)

        # Verify attachment is associated
        attachments = doc.get_attachments()
        assert len(attachments) == 1
        assert doc.attachment_ids == [att_ref.id]

    def test_document_create_with_attachments(self, local_storage: LocalStorage):
        """Test creating document with attachments."""
        att_ref1 = local_storage.create_attachment_from_bytes(
            b"img1", name="fig1.png", mime_type="image/png"
        )
        att_ref2 = local_storage.create_attachment_from_bytes(
            b"img2", name="fig2.png", mime_type="image/png"
        )

        doc_ref = local_storage.create_document(
            name="test_doc_with_attachments",
            data={"results": "ok"},
            attachments=[att_ref1.id, att_ref2.id],
        )

        doc = doc_ref.get()
        assert len(doc.attachment_ids) == 2
        assert att_ref1.id in doc.attachment_ids
        assert att_ref2.id in doc.attachment_ids

    def test_attachment_shared_by_multiple_datasets(self, local_storage: LocalStorage):
        """Test that one attachment can be shared by multiple datasets."""
        att_ref = local_storage.create_attachment_from_bytes(
            b"shared_data", name="shared.txt", mime_type="text/plain"
        )

        ds_ref1 = local_storage.create_dataset(name="ds1", description={})
        ds_ref2 = local_storage.create_dataset(name="ds2", description={})

        ds1 = ds_ref1.get()
        ds2 = ds_ref2.get()

        ds1.add_attachment(att_ref.id)
        ds2.add_attachment(att_ref.id)

        # Both datasets should have the same attachment
        assert len(ds1.get_attachments()) == 1
        assert len(ds2.get_attachments()) == 1
        assert ds1.get_attachments()[0].id == ds2.get_attachments()[0].id

    def test_attachment_shared_by_dataset_and_document(self, local_storage: LocalStorage):
        """Test that one attachment can be shared by dataset and document."""
        att_ref = local_storage.create_attachment_from_bytes(
            b"figure", name="plot.png", mime_type="image/png"
        )

        ds_ref = local_storage.create_dataset(name="ds_with_fig", description={})
        doc_ref = local_storage.create_document(name="doc_with_fig", data={})

        ds = ds_ref.get()
        doc = doc_ref.get()

        ds.add_attachment(att_ref.id)
        doc.add_attachment(att_ref.id)

        assert len(ds.get_attachments()) == 1
        assert len(doc.get_attachments()) == 1


class TestContentRenderer:
    """Test ContentRenderer functionality."""

    def test_extract_attachments(self, local_storage: LocalStorage):
        """Test extracting attachment IDs from content."""
        renderer = ContentRenderer(local_storage)

        content = """
# Report

See figure: ![plot](attachment://123)

And data: [download](attachment://456)
"""
        att_ids = renderer.extract_attachments(content)
        assert att_ids == [123, 456]

    def test_extract_no_attachments(self, local_storage: LocalStorage):
        """Test extracting from content with no attachments."""
        renderer = ContentRenderer(local_storage)

        content = "# Report\n\nNo attachments here."
        att_ids = renderer.extract_attachments(content)
        assert att_ids == []

    def test_render_html_with_attachments(self, local_storage: LocalStorage):
        """Test rendering HTML with attachment references."""
        # Create an attachment
        att_ref = local_storage.create_attachment_from_bytes(
            b"fake_image_data", name="plot.png", mime_type="image/png"
        )

        renderer = ContentRenderer(local_storage)
        content = f"# Report\n\n![plot](attachment://{att_ref.id})"

        html = renderer.render_html(content)

        # Should contain data URL
        assert "data:image/png;base64," in html
        assert "ZmFrZV9pbWFnZV9kYXRh" in html  # base64 of "fake_image_data"

    def test_get_attachment_url_data_format(self, local_storage: LocalStorage):
        """Test getting attachment URL in data format."""
        att_ref = local_storage.create_attachment_from_bytes(
            b"test_data", name="test.txt", mime_type="text/plain"
        )

        renderer = ContentRenderer(local_storage)
        url = renderer.get_attachment_url(att_ref.id, format="data")

        assert url.startswith("data:text/plain;base64,")

    def test_get_attachment_info(self, local_storage: LocalStorage):
        """Test getting attachment info."""
        att_ref = local_storage.create_attachment_from_bytes(
            b"test", name="info.txt", mime_type="text/plain"
        )

        renderer = ContentRenderer(local_storage)
        info = renderer.get_attachment_info(att_ref.id)

        assert info["id"] == att_ref.id
        assert info["name"] == "info.txt"
        assert info["mime_type"] == "text/plain"

    def test_render_attachment_list_html(self, local_storage: LocalStorage):
        """Test rendering attachment list as HTML."""
        att_ref = local_storage.create_attachment_from_bytes(
            b"image", name="fig.png", mime_type="image/png"
        )

        renderer = ContentRenderer(local_storage)
        html = renderer.render_attachment_list([att_ref.id], format="html")

        assert '<div class="attachment image"' in html
        assert "fig.png" in html

    def test_render_attachment_list_markdown(self, local_storage: LocalStorage):
        """Test rendering attachment list as Markdown."""
        att_ref = local_storage.create_attachment_from_bytes(
            b"image", name="fig.png", mime_type="image/png"
        )

        renderer = ContentRenderer(local_storage)
        md = renderer.render_attachment_list([att_ref.id], format="markdown")

        assert f"![fig.png](attachment://{att_ref.id})" == md


class TestIntegration:
    """Integration tests for content and attachments."""

    def test_full_report_workflow(self, local_storage: LocalStorage, tmp_path: Path):
        """Test complete workflow: dataset with content and attachments."""
        # Create dataset
        ds_ref = local_storage.create_dataset(
            name="experiment_001",
            description={"type": "spectroscopy", "qubit": "Q1"},
            config={"frequency": {"start": 5e9, "stop": 5.1e9}},
            content="# Experiment 001\n\nInitial notes...",
        )

        # Create attachment
        att_ref = local_storage.create_attachment_from_bytes(
            b"figure_data", name="spectrum.png", mime_type="image/png"
        )

        # Add attachment to dataset
        ds = ds_ref.get()
        ds.add_attachment(att_ref.id)

        # Update content with attachment reference
        ds.save_content(f"""
# Experiment 001

## Results

![Spectrum](attachment://{att_ref.id})

Frequency range: 5.0 - 5.1 GHz
""")

        # Create analysis document
        doc_ref = local_storage.create_document(
            name="analysis_001",
            data={"fit_result": {"f0": 5.001e9, "Q": 10000}},
            content=f"""
# Analysis of Experiment 001

Based on dataset #{ds.id}

![Spectrum](attachment://{att_ref.id})

The resonator frequency is 5.001 GHz.
""",
            attachments=[att_ref.id],
        )

        # Verify everything is linked correctly
        ds2 = local_storage.get_dataset(ds_ref.id)
        doc2 = local_storage.get_document(doc_ref.id)

        assert ds2.content is not None
        assert len(ds2.get_attachments()) == 1
        assert doc2.content is not None
        assert len(doc2.attachment_ids) == 1

        # Render document to HTML
        renderer = ContentRenderer(local_storage)
        html = renderer.render_html(doc2.content)
        assert "data:image/png;base64," in html

    def test_content_deduplication(self, local_storage: LocalStorage):
        """Test that identical content is deduplicated."""
        content = "# Same Content\n\nThis is identical."

        ds_ref1 = local_storage.create_dataset(
            name="ds1", description={}, content=content
        )
        ds_ref2 = local_storage.create_dataset(
            name="ds2", description={}, content=content
        )

        ds1 = ds_ref1.get()
        ds2 = ds_ref2.get()

        # Both should have content_hash
        assert ds1.content_hash is not None
        assert ds2.content_hash is not None
        # Same content should produce same hash
        assert ds1.content_hash == ds2.content_hash

    def test_document_ref_delete_with_attachments(self, local_storage: LocalStorage):
        """Test that deleting document doesn't delete shared attachment."""
        att_ref = local_storage.create_attachment_from_bytes(
            b"shared", name="shared.txt", mime_type="text/plain"
        )

        doc_ref1 = local_storage.create_document(
            name="doc1", data={}, attachments=[att_ref.id]
        )
        doc_ref2 = local_storage.create_document(
            name="doc2", data={}, attachments=[att_ref.id]
        )

        # Delete first document
        doc_ref1.delete()

        # Attachment should still exist (referenced by doc2)
        att = local_storage.get_attachment(att_ref.id)
        assert att.name == "shared.txt"

    def test_dataset_ref_delete_with_attachments(self, local_storage: LocalStorage):
        """Test that deleting dataset doesn't delete attachment."""
        att_ref = local_storage.create_attachment_from_bytes(
            b"data", name="data.txt", mime_type="text/plain"
        )

        ds_ref = local_storage.create_dataset(name="ds", description={})
        ds = ds_ref.get()
        ds.add_attachment(att_ref.id)

        # Delete dataset
        ds_ref.delete()

        # Attachment should still exist
        att = local_storage.get_attachment(att_ref.id)
        assert att.name == "data.txt"

    def test_attachment_delete_not_allowed_when_referenced(self, local_storage: LocalStorage):
        """Test that attachment cannot be deleted when still referenced."""
        att_ref = local_storage.create_attachment_from_bytes(
            b"data", name="data.txt", mime_type="text/plain"
        )

        ds_ref = local_storage.create_dataset(name="ds", description={})
        ds = ds_ref.get()
        ds.add_attachment(att_ref.id)

        # Try to delete attachment (should return False or still exist)
        att_ref.delete()

        # Attachment should still exist because it's referenced
        att = local_storage.get_attachment(att_ref.id)
        assert att is not None
