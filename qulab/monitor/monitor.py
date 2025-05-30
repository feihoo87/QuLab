"""
QuLab Monitor Module

This module provides real-time data visualization capabilities for QuLab.
It implements a multiprocessing-based monitoring system that can display
multiple data streams in a configurable grid layout.

Classes:
    Monitor: Main class for creating and managing the monitoring window
"""

import multiprocessing as mp
import sys

# try:
#     mp.set_start_method("spawn")
# except:
#     pass


def main(data_queue: mp.Queue,
         num_columns: int = 4,
         minimum_height: int = 400,
         plot_colors: list[tuple[int, int, int]] = []) -> None:
    """
    Initialize and run the main monitoring window.

    Args:
        data_queue: Multiprocessing queue for data communication
        num_columns: Number of columns in the plot grid layout
        minimum_height: Minimum height of each plot in pixels
        plot_colors: List of RGB color tuples for plot lines
    """
    from .mainwindow import MainWindow
    from .qt_compat import QtWidgets

    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow(data_queue, num_columns, minimum_height, plot_colors)
    sys.exit(app.exec())


class Monitor:
    """
    Real-time data monitoring interface.
    
    This class manages a separate process that displays real-time data plots
    in a grid layout. Data can be added through various methods and will be
    displayed immediately.

    Args:
        number_of_columns: Number of columns in the plot grid layout
        minimum_height: Minimum height of each plot in pixels
        colors: List of RGB color tuples for plot lines
    """

    def __init__(self,
                 number_of_columns: int = 4,
                 minimum_height: int = 400,
                 colors: list[tuple[int, int, int]] = []):
        self.colors = [tuple(color) for color in colors]
        self.number_of_columns = number_of_columns
        self.minimum_height = minimum_height
        self.queue = mp.Queue(20)
        self.process = None
        self.start()

    def start(self) -> None:
        """Start the monitoring process if not already running."""
        if self.process is not None and self.process.is_alive():
            return
        self.queue = mp.Queue(20)
        self.process = mp.Process(target=main,
                                args=(self.queue, self.number_of_columns,
                                     self.minimum_height, self.colors))
        self.process.start()

    def _put(self, message: tuple) -> None:
        """Send a message to the monitoring process."""
        self.queue.put(message)

    def roll(self) -> None:
        """Clear and reset all plots."""
        self._put(("ROLL", None))

    def set_column_names(self, *column_names) -> None:
        """Set the names of data columns for plotting."""
        self._put(('PN', list(column_names)))

    def add_point(self, *values) -> None:
        """Add a new data point to the plots."""
        self._put(('PD', list(values)))

    def set_plots(self, plot_config: str) -> None:
        """
        Configure which columns to plot against each other.

        Args:
            plot_config: String specifying plot configurations, e.g. "(x,y)" or "(x1,y1);(x2,y2);"
        """
        self._put(('PXY', str(plot_config)))

    def set_trace_column_names(self, *column_names) -> None:
        """Set the names of trace data columns."""
        self._put(('TN', list(column_names)))

    def add_trace(self, *values) -> None:
        """Add a new trace data point."""
        self._put(('TD', list(values)))

    def set_trace_plots(self, plot_config: str) -> None:
        """
        Configure which columns to plot for traces.

        Args:
            plot_config: String specifying trace plot configurations, e.g. "(x,y)" or "(x1,y1);(x2,y2);"
        """
        self._put(('TXY', str(plot_config)))

    def is_alive(self) -> bool:
        """Check if the monitoring process is running."""
        return self.process.is_alive()

    def __del__(self):
        """Clean up resources when the Monitor object is deleted."""
        try:
            self.process.kill()
        except:
            pass


# Global monitor instance
_monitor = None


def get_monitor(auto_open: bool = True) -> Monitor:
    """
    Get or create a global Monitor instance.

    Args:
        auto_open: If True, create a new Monitor if none exists or if existing one is not running

    Returns:
        Monitor instance
    """
    global _monitor

    if auto_open and (_monitor is None or not _monitor.is_alive()):
        _monitor = Monitor()

    return _monitor


if __name__ == "__main__":
    # Example usage and testing code
    import time
    import numpy as np

    for i in range(3):
        index = 0
        while True:
            if index >= 100:
                break

            m = get_monitor()

            if index == 0:
                m.set_column_names("index", "H", "S")
                m.set_plots("(index,H);(index,S)")
                m.roll()
            m.add_point(index, np.random.randn(), np.sin(index / 20))
            index += 1
            time.sleep(0.2)
