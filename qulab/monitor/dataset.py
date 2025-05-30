"""
QuLab Monitor Dataset Module

This module provides data management functionality for the QuLab monitor application.
It handles storage and retrieval of time-series data with support for both point-by-point
and trace-based data collection.

The Dataset class maintains a rolling buffer of data frames, where each frame can
contain multiple named columns of numerical data.
"""

from collections import defaultdict, deque
from typing import Union, Sequence

from .config import ROLL_BUFFER_SIZE

PAUSE_TIME = 1

Number = Union[int, float, complex]
DataPoint = Union[Number, Sequence[Number]]
DataFrame = Union[Sequence[Number], Sequence[Sequence[Number]]]


def remove_duplicates(input_list: list[str]) -> list[str]:
    """
    Remove duplicates from a list of strings while preserving order.

    Args:
        input_list: List of strings that may contain duplicates

    Returns:
        List of unique strings in their original order
    """
    return list(dict.fromkeys(input_list))


class Dataset:
    """
    A data management class for storing and retrieving time-series data.

    This class maintains a rolling buffer of data frames, where each frame
    contains multiple columns of numerical data. It supports both point-by-point
    data collection and trace-based data collection.

    Attributes:
        column_names: List of column names for the dataset
        box: Rolling buffer containing data frames
        dirty: Flag indicating if data has been modified since last read
    """

    def __init__(self):
        """Initialize an empty dataset with a rolling buffer."""
        self.column_names: list[str] = []
        self.box: deque[dict] = deque(maxlen=ROLL_BUFFER_SIZE)
        self.dirty: bool = True

    def clear(self) -> None:
        """Clear all data from the dataset."""
        self.box.clear()

    def clear_history(self) -> None:
        """
        Clear historical data while preserving the most recent frame.
        
        This is useful for maintaining the current state while discarding
        historical data that is no longer needed.
        """
        if self.box:
            current_frame = self.box.popleft()
            self.box.clear()
            self.box.appendleft(current_frame)

    def set_column_names(self, column_names: list[str]) -> None:
        """
        Set or update the column names for the dataset.

        If the new column names differ from the current ones, all existing
        data will be cleared to maintain consistency.

        Args:
            column_names: List of unique column names
        """
        column_names = remove_duplicates(column_names)
        if column_names != self.column_names:
            self.clear()
        self.column_names = column_names

    def get_data(self, step: int, x_name: str,
                 y_name: str) -> tuple[list[Number], list[Number]]:
        """
        Retrieve X-Y data pairs from a specific step in the dataset.

        Args:
            step: Index of the data frame to retrieve
            x_name: Name of the column to use for X values
            y_name: Name of the column to use for Y values

        Returns:
            Tuple containing lists of X and Y values. Returns empty lists if
            the requested step is not available.
        """
        try:
            frame = self.box[step]
            return frame[x_name], frame[y_name]
        except IndexError:
            return [], []

    def append(self, dataframe: DataFrame) -> None:
        """
        Append new data to the dataset.

        This method automatically determines whether the input is point data
        or trace data based on its structure.

        Args:
            dataframe: Either a list of values for point data or a list of
                      lists for trace data. The length must match the number
                      of columns.

        Raises:
            AssertionError: If the input data length doesn't match the number
                           of columns.
            TypeError: If the input data format is invalid.
        """
        if not dataframe:
            return
        try:
            # Test if dataframe is a list of lists (trace data)
            iter(dataframe[0])
            self._append_traces(dataframe)
        except TypeError:
            self._append_points(dataframe)

    def roll(self) -> None:
        """
        Add a new empty frame to the dataset.
        
        This creates a new defaultdict that will automatically create empty
        lists for any new column names accessed.
        """
        self.box.appendleft(defaultdict(list))

    def _append_points(self, points: Sequence[Number]) -> None:
        """
        Append point data to the current frame.

        Args:
            points: List of values, one for each column

        Raises:
            AssertionError: If the number of points doesn't match the number
                           of columns
        """
        self.dirty = True
        if len(points) != len(self.column_names):
            raise AssertionError(
                "Point data length mismatch\n"
                f"Expected {len(self.column_names)} values for columns: {self.column_names}\n"
                f"Received {len(points)} values: {points}"
            )
        
        for name, value in zip(self.column_names, points):
            self.box[0][name].append(value)

    def _append_traces(self, traces: Sequence[Sequence[Number]]) -> None:
        """
        Append trace data as a new frame.

        Args:
            traces: List of data sequences, one for each column

        Raises:
            AssertionError: If the number of traces doesn't match the number
                           of columns
        """
        self.dirty = True
        if len(traces) != len(self.column_names):
            raise AssertionError(
                "Trace data length mismatch\n"
                f"Expected {len(self.column_names)} sequences for columns: {self.column_names}\n"
                f"Received {len(traces)} sequences"
            )
        
        self.box.appendleft(dict(zip(self.column_names, traces)))
