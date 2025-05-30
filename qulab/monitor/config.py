"""
QuLab Monitor Configuration Module

This module defines the global configuration settings for the QuLab monitor
application, including:
- Visual styles and themes
- Data transformation functions
- Plot appearance settings
- Buffer sizes and indices

The configuration values are used throughout the monitor application to maintain
consistent appearance and behavior.
"""

from typing import Callable, Dict, List, Tuple, Union
import numpy as np

# Qt stylesheet for the application
STYLE = '''
QWidget {
    font: medium Ubuntu;
    background-color: #011F2F;
    font-size: 16px;
    color: #FFFFFF;
}
'''

# Number of data frames to keep in the rolling buffer
ROLL_BUFFER_SIZE = 6

# Data transformation functions for complex data visualization
DataTransform = Callable[[Union[np.ndarray, list], float], np.ndarray]

TRANSFORMS: Dict[str, DataTransform] = {
    "mag": lambda data, _: np.abs(data),
    "phase": lambda data, _: np.angle(data),
    "real": lambda data, _: np.real(data),
    "imag": lambda data, _: np.imag(data),
    "rot": lambda data, angle: np.real(np.exp(1j * angle) * np.array(data))
}

# List of available transformation names
TRANSFORM_NAMES: List[str] = list(TRANSFORMS.keys())

# Colors for selected and unselected states (RGB values)
COLOR_SELECTED: Tuple[int, int, int] = (0, 0, 0)
COLOR_UNSELECTED: Tuple[int, int, int] = (6, 6, 8)

# Default colors for plot lines (RGB values)
DEFAULT_COLORS: List[Tuple[int, int, int]] = [
    (200, 0, 0),    # Bright red
    (55, 100, 180), # Blue
    (40, 80, 150),  # Medium blue
    (30, 50, 110),  # Dark blue
    (25, 40, 70),   # Navy
    (25, 30, 50),   # Dark navy
]

# Line widths for each plot line
LINE_WIDTHS: List[int] = [3, 2, 2, 2, 1, 1]

# Symbol sizes for each plot line (0 means no symbols)
SYMBOL_SIZES: List[int] = [5, 0, 0, 0, 0, 0]

# Reversed indices for the rolling buffer (newest to oldest)
ROLL_INDICES: List[int] = list(range(ROLL_BUFFER_SIZE))[::-1]
