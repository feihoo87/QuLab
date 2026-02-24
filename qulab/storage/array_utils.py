"""Array utilities - pattern detection and generation for optimized storage.

This module provides functions to detect if an array can be represented
by simple generation functions (linspace, logspace, etc.) and to generate
arrays from stored parameters.
"""

import numpy as np


def detect_array_pattern(arr: np.ndarray) -> dict | None:
    """Detect if an array can be represented by simple generation functions.

    Supported patterns:
    1. linspace: Arithmetic sequence (evenly spaced values)
    2. logspace: Geometric sequence (logarithmically spaced values)
    3. arange: Integer step sequence
    4. full: Constant array
    5. None: Cannot be simply generated, store full data

    Args:
        arr: NumPy array to analyze

    Returns:
        Dict with 'type' and 'params' keys, or None if no pattern detected
    """
    arr = np.asarray(arr)

    if arr.size == 0:
        return None

    # Handle multi-dimensional arrays - flatten for pattern detection
    # but keep original shape in params for full storage
    flat_arr = arr.ravel()

    # Detection requires at least 2 elements
    if len(flat_arr) < 2:
        return None

    # Detect full: constant array
    if np.allclose(flat_arr, flat_arr[0], rtol=1e-10):
        return {
            "type": "full",
            "params": {
                "shape": list(arr.shape),
                "fill_value": float(flat_arr[0]) if arr.size > 0 else 0.0,
                "dtype": str(arr.dtype)
            }
        }

    # Detect linspace: arithmetic sequence (evenly spaced)
    diff = np.diff(flat_arr)
    if np.allclose(diff, diff[0], rtol=1e-10) and diff[0] != 0:
        return {
            "type": "linspace",
            "params": {
                "start": float(flat_arr[0]),
                "stop": float(flat_arr[-1]),
                "num": len(flat_arr),
                "dtype": str(arr.dtype)
            }
        }

    # Detect logspace: geometric sequence (logarithmically spaced)
    # All values must be positive for logspace detection
    if np.all(flat_arr > 0):
        log_arr = np.log(flat_arr)
        log_diff = np.diff(log_arr)
        if np.allclose(log_diff, log_diff[0], rtol=1e-10) and log_diff[0] != 0:
            return {
                "type": "logspace",
                "params": {
                    "start": float(log_arr[0]),
                    "stop": float(log_arr[-1]),
                    "num": len(flat_arr),
                    "base": np.e,
                    "dtype": str(arr.dtype)
                }
            }

    # Detect arange: integer step sequence
    # This is similar to linspace but we check if step is more "natural"
    if np.allclose(diff, diff[0], rtol=1e-10) and diff[0] != 0:
        step = diff[0]
        # Only mark as arange if step is a "nice" number
        # (integer or simple fraction)
        if abs(step - round(step)) < 1e-10 or abs(step) >= 1:
            return {
                "type": "arange",
                "params": {
                    "start": float(flat_arr[0]),
                    "stop": float(flat_arr[-1] + step),
                    "step": float(step),
                    "dtype": str(arr.dtype)
                }
            }

    # No pattern detected
    return None


def generate_from_pattern(pattern: dict) -> np.ndarray:
    """Generate an array from stored pattern parameters.

    Args:
        pattern: Dict with 'type' and 'params' keys

    Returns:
        Generated NumPy array

    Raises:
        ValueError: If pattern type is unknown
    """
    ptype = pattern["type"]
    params = pattern["params"]
    dtype = np.dtype(params.get("dtype", "float64"))

    if ptype == "linspace":
        return np.linspace(
            params["start"],
            params["stop"],
            params["num"],
            dtype=dtype
        )
    elif ptype == "logspace":
        base = params.get("base", 10.0)
        return np.logspace(
            params["start"],
            params["stop"],
            params["num"],
            base=base,
            dtype=dtype
        )
    elif ptype == "arange":
        return np.arange(
            params["start"],
            params["stop"],
            params["step"],
            dtype=dtype
        )
    elif ptype == "full":
        shape = tuple(params["shape"])
        return np.full(shape, params["fill_value"], dtype=dtype)
    else:
        raise ValueError(f"Unknown pattern type: {ptype}")


def compute_index(pattern: dict, index: int | slice) -> float | np.ndarray:
    """Compute value at index directly from pattern without generating full array.

    This is more memory-efficient than generating the entire array when
    only a single value or small slice is needed.

    Args:
        pattern: Dict with 'type' and 'params' keys
        index: Integer index or slice

    Returns:
        Computed value(s) at the specified index

    Raises:
        IndexError: If index is out of range
    """
    ptype = pattern["type"]
    params = pattern["params"]

    if ptype == "linspace":
        num = params["num"]
        start, stop = params["start"], params["stop"]

        if isinstance(index, int):
            if index < 0:
                index += num
            if not (0 <= index < num):
                raise IndexError(f"Index {index} out of range [0, {num})")
            return start + index * (stop - start) / (num - 1)
        elif isinstance(index, slice):
            indices = range(*index.indices(num))
            return np.array([
                start + i * (stop - start) / (num - 1)
                for i in indices
            ])
        else:
            raise TypeError(f"Index must be int or slice, got {type(index)}")

    elif ptype == "logspace":
        num = params["num"]
        start, stop = params["start"], params["stop"]
        base = params.get("base", 10.0)

        if isinstance(index, int):
            if index < 0:
                index += num
            if not (0 <= index < num):
                raise IndexError(f"Index {index} out of range [0, {num})")
            return base ** (start + index * (stop - start) / (num - 1))
        elif isinstance(index, slice):
            indices = range(*index.indices(num))
            return np.array([
                base ** (start + i * (stop - start) / (num - 1))
                for i in indices
            ])
        else:
            raise TypeError(f"Index must be int or slice, got {type(index)}")

    elif ptype == "arange":
        start, step = params["start"], params["step"]
        stop = params["stop"]
        num = int((stop - start) / step)

        if isinstance(index, int):
            if index < 0:
                index += num
            if not (0 <= index < num):
                raise IndexError(f"Index {index} out of range [0, {num})")
            return start + index * step
        elif isinstance(index, slice):
            indices = range(*index.indices(num))
            return np.array([start + i * step for i in indices])
        else:
            raise TypeError(f"Index must be int or slice, got {type(index)}")

    elif ptype == "full":
        fill_value = params["fill_value"]
        shape = tuple(params["shape"])
        total_size = np.prod(shape) if shape else 1

        if isinstance(index, int):
            if index < 0:
                index += total_size
            if not (0 <= index < total_size):
                raise IndexError(f"Index {index} out of range [0, {total_size})")
            return fill_value
        elif isinstance(index, slice):
            indices = range(*index.indices(total_size))
            return np.full(len(indices), fill_value)
        else:
            raise TypeError(f"Index must be int or slice, got {type(index)}")

    else:
        raise ValueError(f"Unknown pattern type: {ptype}")


def compute_shape(pattern: dict) -> tuple:
    """Get the shape of an array from its pattern.

    Args:
        pattern: Dict with 'type' and 'params' keys

    Returns:
        Shape tuple
    """
    ptype = pattern["type"]
    params = pattern["params"]

    if ptype == "full":
        return tuple(params["shape"])
    elif ptype in ("linspace", "logspace", "arange"):
        if ptype == "arange":
            start, step = params["start"], params["step"]
            stop = params["stop"]
            num = int((stop - start) / step)
        else:
            num = params["num"]
        return (num,)
    else:
        raise ValueError(f"Unknown pattern type: {ptype}")
