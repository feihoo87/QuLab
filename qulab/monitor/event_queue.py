"""
QuLab Monitor Event Queue Module

This module implements an event handling system for the QuLab monitor application.
It processes commands and data received through a multiprocessing queue to update
the monitor's display and datasets.

The event queue handles various types of commands:
- PN/TN: Set column names for point/trace data
- PD/TD: Append point/trace data
- ROLL: Create new data frame
- PXY/TXY: Update plot configurations
"""

import warnings
from multiprocessing import Queue
from typing import Any, Literal, Tuple, Union

from .dataset import Dataset
from .toolbar import ToolBar

# Type definitions
CommandType = Literal["PN", "TN", "PD", "TD", "ROLL", "PXY", "TXY"]
DataType = Union[list[str], list[float], str, None]
EventType = Tuple[CommandType, DataType]


class EventQueue:
    """
    Event handler for processing monitor commands and data.

    This class manages the communication between the data collection process
    and the monitor display. It receives commands and data through a queue
    and updates the appropriate components of the monitor.

    Attributes:
        toolbar: The monitor's toolbar for UI controls
        queue: Multiprocessing queue for receiving commands and data
        point_dataset: Dataset for point-by-point data collection
        trace_dataset: Dataset for trace-based data collection
    """

    def __init__(self, queue: Queue, toolbar: ToolBar, point_dataset: Dataset,
                 trace_dataset: Dataset):
        """
        Initialize the event queue.

        Args:
            queue: Multiprocessing queue for receiving commands
            toolbar: Monitor's toolbar instance
            point_dataset: Dataset for point data
            trace_dataset: Dataset for trace data
        """
        self.toolbar = toolbar
        self.queue = queue
        self.point_dataset = point_dataset
        self.trace_dataset = trace_dataset

    def flush(self) -> None:
        """
        Process all pending events in the queue.

        This method retrieves and processes all available events from the queue.
        Each event should be a tuple containing a command string and associated data.
        Invalid events are logged as warnings and skipped.
        """
        while not self.queue.empty():
            try:
                event = self.queue.get()
                if not isinstance(event, tuple):
                    raise ValueError("Queue event must be a tuple")
                if len(event) != 2:
                    raise ValueError("Queue event must contain exactly two elements (command, data)")
                
                command, data = event
                if not isinstance(command, str):
                    raise ValueError("Command must be a string")
                
                self.handle(command, data)
                
            except (ValueError, AssertionError) as error:
                warnings.warn(f"Invalid event format: {error}")
                continue

    def handle(self, command: str, data: Any) -> None:
        """
        Process a single event based on its command type.

        Args:
            command: String identifying the type of event
            data: Data associated with the event

        The following commands are supported:
            PN: Set point data column names
            TN: Set trace data column names
            PD: Append point data
            TD: Append trace data
            ROLL: Create new data frame
            PXY: Update point plot configuration
            TXY: Update trace plot configuration
        """
        match command:
            case "PN":  # Set point data column names
                self.point_dataset.set_column_names(data)
                self.toolbar.refresh_comb()
                
            case "TN":  # Set trace data column names
                self.trace_dataset.set_column_names(data)
                self.toolbar.refresh_comb()
                
            case "PD":  # Append point data
                self.point_dataset.append(data)
                
            case "TD":  # Append trace data
                self.trace_dataset.append(data)
                
            case "ROLL":  # Create new data frame
                self.point_dataset.roll()
                
            case "PXY":  # Update point plot configuration
                self.toolbar.set_point_text(data)
                
            case "TXY":  # Update trace plot configuration
                self.toolbar.set_trace_text(data)
                
            case _:
                warnings.warn(f"Unknown command: {command}")
