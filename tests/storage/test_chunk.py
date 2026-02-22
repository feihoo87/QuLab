"""Tests for content-addressed chunk storage."""

import hashlib
import zlib
from pathlib import Path

import pytest

from qulab.storage.chunk import (
    delete_chunk,
    get_data_path,
    load_chunk,
    save_chunk,
    set_data_path,
)


class TestChunk:
    """Test content-addressed chunk storage."""

    def test_save_chunk(self, temp_storage_path: Path):
        """Test saving a data chunk and verifying path and hash."""
        set_data_path(str(temp_storage_path))
        data = b"Hello, World! This is test data."

        rel_path, size = save_chunk(data, compressed=False, base_path=temp_storage_path)

        # Verify size (returns size of stored data)
        assert size == len(data)

        # Verify path structure (chunks/xx/yy/full_hash)
        path_parts = rel_path.parts
        assert path_parts[0] == "chunks"
        assert len(path_parts[1]) == 2  # First 2 chars of hash
        assert len(path_parts[2]) == 2  # Next 2 chars of hash
        assert len(path_parts[3]) == 40  # Full 40 chars of SHA1

        # Verify file exists
        full_path = temp_storage_path / rel_path
        assert full_path.exists()
        assert full_path.read_bytes() == data

    def test_save_chunk_compressed(self, temp_storage_path: Path):
        """Test saving a compressed data chunk."""
        set_data_path(str(temp_storage_path))
        data = b"Hello, World! " * 1000  # Larger data for compression benefit

        rel_path, size = save_chunk(data, compressed=True, base_path=temp_storage_path)

        # Verify compressed size is returned (not original size)
        assert size < len(data)  # Should be compressed

        # Verify file exists and contains compressed data
        full_path = temp_storage_path / rel_path
        assert full_path.exists()

        # Compressed data should be different from original
        file_content = full_path.read_bytes()
        assert file_content != data

        # Verify it can be decompressed
        decompressed = zlib.decompress(file_content)
        assert decompressed == data

    def test_load_chunk(self, temp_storage_path: Path):
        """Test loading a data chunk."""
        set_data_path(str(temp_storage_path))
        data = b"Test data for loading"

        rel_path, _ = save_chunk(data, compressed=False, base_path=temp_storage_path)

        # Load by relative path
        loaded = load_chunk(str(rel_path), compressed=False, base_path=temp_storage_path)
        assert loaded == data

    def test_load_chunk_compressed(self, temp_storage_path: Path):
        """Test loading a compressed data chunk."""
        set_data_path(str(temp_storage_path))
        data = b"Compressed test data" * 100

        rel_path, _ = save_chunk(data, compressed=True, base_path=temp_storage_path)

        # Load compressed data
        loaded = load_chunk(str(rel_path), compressed=True, base_path=temp_storage_path)
        assert loaded == data

    def test_content_addressing(self, temp_storage_path: Path):
        """Test that same content returns same hash/path."""
        set_data_path(str(temp_storage_path))
        data = b"Identical content"

        # Save same data twice
        rel_path1, size1 = save_chunk(data, compressed=False, base_path=temp_storage_path)
        rel_path2, size2 = save_chunk(data, compressed=False, base_path=temp_storage_path)

        # Should get same path and size
        assert rel_path1 == rel_path2
        assert size1 == size2

        # Verify hash is correct SHA1
        expected_hash = hashlib.sha1(data).hexdigest()
        path_str = str(rel_path1)
        # Extract hash from path (chunks/xx/yy/zzzz...)
        # Path format: chunks/ab/cd/abcdef... (40 chars total)
        # stored_hash is the filename portion (40 chars)
        stored_hash = rel_path1.name
        assert stored_hash == expected_hash

    def test_load_chunk_not_found(self, temp_storage_path: Path):
        """Test loading a non-existent chunk raises FileNotFoundError."""
        set_data_path(str(temp_storage_path))

        with pytest.raises(FileNotFoundError):
            load_chunk("chunks/ab/cd/nonexistent_hash", base_path=temp_storage_path)

    def test_delete_chunk(self, temp_storage_path: Path):
        """Test deleting a chunk."""
        set_data_path(str(temp_storage_path))
        data = b"Data to be deleted"

        rel_path, _ = save_chunk(data, compressed=False, base_path=temp_storage_path)
        full_path = temp_storage_path / rel_path

        assert full_path.exists()

        delete_chunk(str(rel_path))

        assert not full_path.exists()

    def test_delete_chunk_nonexistent(self, temp_storage_path: Path):
        """Test deleting a non-existent chunk raises FileNotFoundError."""
        set_data_path(str(temp_storage_path))
        # Should raise FileNotFoundError
        with pytest.raises(FileNotFoundError):
            delete_chunk("chunks/ab/cd/nonexistent")

    def test_set_get_data_path(self, temp_storage_path: Path):
        """Test setting and getting data path."""
        set_data_path(str(temp_storage_path))
        assert get_data_path() == temp_storage_path

    def test_save_different_content_different_paths(self, temp_storage_path: Path):
        """Test different content gets different paths."""
        set_data_path(str(temp_storage_path))
        data1 = b"Content A"
        data2 = b"Content B"

        rel_path1, _ = save_chunk(data1, compressed=False, base_path=temp_storage_path)
        rel_path2, _ = save_chunk(data2, compressed=False, base_path=temp_storage_path)

        assert rel_path1 != rel_path2

    def test_save_empty_data(self, temp_storage_path: Path):
        """Test saving empty data."""
        set_data_path(str(temp_storage_path))
        data = b""

        rel_path, size = save_chunk(data, compressed=False, base_path=temp_storage_path)

        assert size == 0
        loaded = load_chunk(str(rel_path), base_path=temp_storage_path)
        assert loaded == b""

    def test_save_large_data(self, temp_storage_path: Path):
        """Test saving large data."""
        set_data_path(str(temp_storage_path))
        data = b"x" * (1024 * 1024 * 5)  # 5MB

        rel_path, size = save_chunk(data, compressed=False, base_path=temp_storage_path)

        assert size == len(data)
        loaded = load_chunk(str(rel_path), base_path=temp_storage_path)
        assert loaded == data

    def test_load_chunk_with_path_object(self, temp_storage_path: Path):
        """Test loading with Path object."""
        set_data_path(str(temp_storage_path))
        data = b"Test with Path object"

        rel_path, _ = save_chunk(data, compressed=False, base_path=temp_storage_path)

        # Load using Path object
        loaded = load_chunk(rel_path, compressed=False, base_path=temp_storage_path)
        assert loaded == data
