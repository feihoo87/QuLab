"""Tests for array_utils module - pattern detection and generation."""

import numpy as np
import pytest

from qulab.storage.array_utils import (
    compute_index,
    compute_shape,
    detect_array_pattern,
    generate_from_pattern,
)


class TestDetectArrayPattern:
    """Test pattern detection for various array types."""

    def test_detect_linspace(self):
        """Test detection of linspace arrays."""
        arr = np.linspace(0, 10, 101)
        pattern = detect_array_pattern(arr)

        assert pattern is not None
        assert pattern["type"] == "linspace"
        assert pattern["params"]["start"] == 0.0
        assert pattern["params"]["stop"] == 10.0
        assert pattern["params"]["num"] == 101

    def test_detect_linspace_negative(self):
        """Test detection of linspace with negative values."""
        arr = np.linspace(-5, -1, 50)
        pattern = detect_array_pattern(arr)

        assert pattern is not None
        assert pattern["type"] == "linspace"
        assert pattern["params"]["start"] == -5.0
        assert pattern["params"]["stop"] == -1.0
        assert pattern["params"]["num"] == 50

    def test_detect_linspace_mixed(self):
        """Test detection of linspace with mixed positive/negative values."""
        arr = np.linspace(-1, 1, 101)
        pattern = detect_array_pattern(arr)

        assert pattern is not None
        assert pattern["type"] == "linspace"
        assert abs(pattern["params"]["start"] - (-1.0)) < 1e-10
        assert abs(pattern["params"]["stop"] - 1.0) < 1e-10
        assert pattern["params"]["num"] == 101

    def test_detect_logspace(self):
        """Test detection of logspace arrays."""
        arr = np.logspace(1, 3, 100)
        pattern = detect_array_pattern(arr)

        assert pattern is not None
        assert pattern["type"] == "logspace"
        # Note: detection uses np.log() which is natural log, so base is np.e
        assert pattern["params"]["base"] == np.e
        assert pattern["params"]["num"] == 100

    def test_detect_logspace_base_e(self):
        """Test detection of logspace with base e."""
        arr = np.logspace(0, 5, 50, base=np.e)
        pattern = detect_array_pattern(arr)

        assert pattern is not None
        assert pattern["type"] == "logspace"
        assert pattern["params"]["base"] == np.e

    def test_detect_arange(self):
        """Test detection of arange arrays."""
        arr = np.arange(0, 10, 0.5)
        pattern = detect_array_pattern(arr)

        # Note: arange might be detected as linspace if step is uniform
        assert pattern is not None
        assert pattern["type"] in ["linspace", "arange"]

    def test_detect_full(self):
        """Test detection of constant (full) arrays."""
        arr = np.full((10,), 5.0)
        pattern = detect_array_pattern(arr)

        assert pattern is not None
        assert pattern["type"] == "full"
        assert pattern["params"]["fill_value"] == 5.0
        assert pattern["params"]["shape"] == [10]

    def test_detect_full_multidim(self):
        """Test detection of multidimensional constant arrays."""
        arr = np.full((3, 4, 5), 2.5)
        pattern = detect_array_pattern(arr)

        assert pattern is not None
        assert pattern["type"] == "full"
        assert pattern["params"]["fill_value"] == 2.5
        assert pattern["params"]["shape"] == [3, 4, 5]

    def test_detect_none_random(self):
        """Test that random arrays return None."""
        np.random.seed(42)
        arr = np.random.rand(100)
        pattern = detect_array_pattern(arr)

        assert pattern is None

    def test_detect_none_irregular(self):
        """Test that irregular arrays return None."""
        arr = np.array([0, 1, 3, 6, 10])  # Triangular numbers
        pattern = detect_array_pattern(arr)

        assert pattern is None

    def test_detect_single_element(self):
        """Test that single element arrays return None."""
        arr = np.array([5.0])
        pattern = detect_array_pattern(arr)

        # Single element arrays can't have a pattern
        assert pattern is None

    def test_detect_two_elements(self):
        """Test detection of two-element arrays."""
        arr = np.array([0.0, 1.0])
        pattern = detect_array_pattern(arr)

        assert pattern is not None
        # Two elements are always "linspace-like"
        assert pattern["type"] == "linspace"


class TestGenerateFromPattern:
    """Test array generation from stored patterns."""

    def test_generate_linspace(self):
        """Test generation of linspace arrays."""
        pattern = {
            "type": "linspace",
            "params": {
                "start": 0.0,
                "stop": 10.0,
                "num": 11,
                "dtype": "float64"
            }
        }
        arr = generate_from_pattern(pattern)
        expected = np.linspace(0, 10, 11)

        np.testing.assert_array_almost_equal(arr, expected)

    def test_generate_logspace(self):
        """Test generation of logspace arrays."""
        pattern = {
            "type": "logspace",
            "params": {
                "start": 0.0,
                "stop": 2.0,
                "num": 10,
                "base": 10.0,
                "dtype": "float64"
            }
        }
        arr = generate_from_pattern(pattern)
        expected = np.logspace(0, 2, 10)

        np.testing.assert_array_almost_equal(arr, expected)

    def test_generate_logspace_base_e(self):
        """Test generation of logspace with base e."""
        pattern = {
            "type": "logspace",
            "params": {
                "start": 0.0,
                "stop": 5.0,
                "num": 50,
                "base": np.e,
                "dtype": "float64"
            }
        }
        arr = generate_from_pattern(pattern)
        expected = np.logspace(0, 5, 50, base=np.e)

        np.testing.assert_array_almost_equal(arr, expected)

    def test_generate_arange(self):
        """Test generation of arange arrays."""
        pattern = {
            "type": "arange",
            "params": {
                "start": 0.0,
                "stop": 10.0,
                "step": 2.0,
                "dtype": "float64"
            }
        }
        arr = generate_from_pattern(pattern)
        expected = np.arange(0, 10, 2)

        np.testing.assert_array_almost_equal(arr, expected)

    def test_generate_full(self):
        """Test generation of full arrays."""
        pattern = {
            "type": "full",
            "params": {
                "shape": [3, 4],
                "fill_value": 5.0,
                "dtype": "float64"
            }
        }
        arr = generate_from_pattern(pattern)
        expected = np.full((3, 4), 5.0)

        np.testing.assert_array_almost_equal(arr, expected)

    def test_generate_unknown_type(self):
        """Test that unknown pattern types raise ValueError."""
        pattern = {
            "type": "unknown",
            "params": {}
        }

        with pytest.raises(ValueError, match="Unknown pattern type"):
            generate_from_pattern(pattern)


class TestComputeIndex:
    """Test direct index computation without array generation."""

    def test_compute_index_linspace_int(self):
        """Test integer indexing on linspace pattern."""
        pattern = {
            "type": "linspace",
            "params": {
                "start": 0.0,
                "stop": 10.0,
                "num": 11,
                "dtype": "float64"
            }
        }

        assert compute_index(pattern, 0) == 0.0
        assert compute_index(pattern, 5) == 5.0
        assert compute_index(pattern, 10) == 10.0

    def test_compute_index_linspace_negative(self):
        """Test negative indexing on linspace pattern."""
        pattern = {
            "type": "linspace",
            "params": {
                "start": 0.0,
                "stop": 10.0,
                "num": 11,
                "dtype": "float64"
            }
        }

        assert compute_index(pattern, -1) == 10.0
        assert compute_index(pattern, -11) == 0.0

    def test_compute_index_linspace_out_of_range(self):
        """Test out of range indexing raises IndexError."""
        pattern = {
            "type": "linspace",
            "params": {
                "start": 0.0,
                "stop": 10.0,
                "num": 11,
                "dtype": "float64"
            }
        }

        with pytest.raises(IndexError):
            compute_index(pattern, 11)

        with pytest.raises(IndexError):
            compute_index(pattern, -12)

    def test_compute_slice_linspace(self):
        """Test slice indexing on linspace pattern."""
        pattern = {
            "type": "linspace",
            "params": {
                "start": 0.0,
                "stop": 10.0,
                "num": 11,
                "dtype": "float64"
            }
        }

        result = compute_index(pattern, slice(0, 3))
        expected = np.array([0.0, 1.0, 2.0])
        np.testing.assert_array_almost_equal(result, expected)

    def test_compute_slice_linspace_middle(self):
        """Test slice in middle of linspace."""
        pattern = {
            "type": "linspace",
            "params": {
                "start": -1.0,
                "stop": 1.0,
                "num": 101,
                "dtype": "float64"
            }
        }

        result = compute_index(pattern, slice(49, 52))
        expected = np.array([-0.02, 0.0, 0.02])
        np.testing.assert_array_almost_equal(result, expected)

    def test_compute_index_logspace(self):
        """Test integer indexing on logspace pattern."""
        pattern = {
            "type": "logspace",
            "params": {
                "start": 0.0,
                "stop": 2.0,
                "num": 11,
                "base": 10.0,
                "dtype": "float64"
            }
        }

        assert abs(compute_index(pattern, 0) - 1.0) < 1e-10
        assert abs(compute_index(pattern, 10) - 100.0) < 1e-8

    def test_compute_slice_logspace(self):
        """Test slice indexing on logspace pattern."""
        pattern = {
            "type": "logspace",
            "params": {
                "start": 0.0,
                "stop": 2.0,
                "num": 11,
                "base": 10.0,
                "dtype": "float64"
            }
        }

        result = compute_index(pattern, slice(0, 3))
        expected = np.logspace(0, 2, 11)[:3]
        np.testing.assert_array_almost_equal(result, expected)

    def test_compute_index_arange(self):
        """Test integer indexing on arange pattern."""
        pattern = {
            "type": "arange",
            "params": {
                "start": 0.0,
                "stop": 10.0,
                "step": 2.0,
                "dtype": "float64"
            }
        }

        assert compute_index(pattern, 0) == 0.0
        assert compute_index(pattern, 1) == 2.0
        assert compute_index(pattern, 4) == 8.0

    def test_compute_index_full(self):
        """Test integer indexing on full pattern."""
        pattern = {
            "type": "full",
            "params": {
                "shape": [10],
                "fill_value": 5.0,
                "dtype": "float64"
            }
        }

        assert compute_index(pattern, 0) == 5.0
        assert compute_index(pattern, 5) == 5.0
        assert compute_index(pattern, -1) == 5.0

    def test_compute_slice_full(self):
        """Test slice indexing on full pattern."""
        pattern = {
            "type": "full",
            "params": {
                "shape": [10],
                "fill_value": 5.0,
                "dtype": "float64"
            }
        }

        result = compute_index(pattern, slice(0, 3))
        expected = np.array([5.0, 5.0, 5.0])
        np.testing.assert_array_almost_equal(result, expected)

    def test_compute_index_invalid_type(self):
        """Test that invalid index types raise TypeError."""
        pattern = {
            "type": "linspace",
            "params": {
                "start": 0.0,
                "stop": 10.0,
                "num": 11,
                "dtype": "float64"
            }
        }

        with pytest.raises(TypeError):
            compute_index(pattern, "invalid")


class TestComputeShape:
    """Test shape computation from patterns."""

    def test_shape_linspace(self):
        """Test shape from linspace pattern."""
        pattern = {
            "type": "linspace",
            "params": {
                "start": 0.0,
                "stop": 10.0,
                "num": 101,
                "dtype": "float64"
            }
        }

        assert compute_shape(pattern) == (101,)

    def test_shape_logspace(self):
        """Test shape from logspace pattern."""
        pattern = {
            "type": "logspace",
            "params": {
                "start": 0.0,
                "stop": 2.0,
                "num": 50,
                "base": 10.0,
                "dtype": "float64"
            }
        }

        assert compute_shape(pattern) == (50,)

    def test_shape_arange(self):
        """Test shape from arange pattern."""
        pattern = {
            "type": "arange",
            "params": {
                "start": 0.0,
                "stop": 10.0,
                "step": 0.5,
                "dtype": "float64"
            }
        }

        assert compute_shape(pattern) == (20,)

    def test_shape_full(self):
        """Test shape from full pattern."""
        pattern = {
            "type": "full",
            "params": {
                "shape": [3, 4, 5],
                "fill_value": 1.0,
                "dtype": "float64"
            }
        }

        assert compute_shape(pattern) == (3, 4, 5)

    def test_shape_unknown(self):
        """Test that unknown pattern types raise ValueError."""
        pattern = {
            "type": "unknown",
            "params": {}
        }

        with pytest.raises(ValueError, match="Unknown pattern type"):
            compute_shape(pattern)


class TestRoundTrip:
    """Test round-trip: detect -> generate -> verify."""

    def test_roundtrip_linspace(self):
        """Test full round-trip for linspace."""
        original = np.linspace(-1, 1, 101)
        pattern = detect_array_pattern(original)
        regenerated = generate_from_pattern(pattern)

        np.testing.assert_array_almost_equal(original, regenerated)

    def test_roundtrip_logspace(self):
        """Test full round-trip for logspace."""
        original = np.logspace(1, 3, 100)
        pattern = detect_array_pattern(original)
        regenerated = generate_from_pattern(pattern)

        np.testing.assert_array_almost_equal(original, regenerated)

    def test_roundtrip_full(self):
        """Test full round-trip for full array."""
        original = np.full((5, 10), 3.14)
        pattern = detect_array_pattern(original)
        regenerated = generate_from_pattern(pattern)

        np.testing.assert_array_almost_equal(original, regenerated)
