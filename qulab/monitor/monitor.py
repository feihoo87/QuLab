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
from typing import cast

import zmq

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
    from .qt_compat import QtWidgets  # type: ignore

    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow(data_queue, num_columns, minimum_height,
                             plot_colors)
    sys.exit(app.exec())


class MonitorUI:
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
        return self.process is not None and self.process.is_alive()

    def __del__(self):
        """Clean up resources when the Monitor object is deleted."""
        try:
            cast(mp.Process, self.process).kill()
        except:
            pass


class Monitor:

    def __init__(self, address: str = "127.0.0.1", port: int = 5555):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{address}:{port}")

    def _send_command(self, cmd: str, data=None) -> None:
        try:
            self.socket.send_pyobj((cmd, data))
            response = self.socket.recv_string()
            if response.startswith("Error"):
                raise RuntimeError(response)
        except Exception as e:
            raise RuntimeError(f"Failed to send command: {str(e)}")

    def roll(self) -> None:
        self._send_command("ROLL", None)

    def set_column_names(self, *column_names) -> None:
        self._send_command("PN", list(column_names))

    def add_point(self, *values) -> None:
        self._send_command("PD", list(values))

    def set_plots(self, plot_config: str) -> None:
        self._send_command("PXY", plot_config)

    def set_trace_column_names(self, *column_names) -> None:
        self._send_command("TN", list(column_names))

    def add_trace(self, *values) -> None:
        self._send_command("TD", list(values))

    def set_trace_plots(self, plot_config: str) -> None:
        self._send_command("TXY", plot_config)

    def __del__(self):
        try:
            self.socket.close()
            self.context.term()
        except:
            pass


class MonitorServer:

    def __init__(self,
                 address: str = "*",
                 port: int = 5555,
                 number_of_columns: int = 4,
                 minimum_height: int = 400,
                 colors: list[tuple[int, int, int]] = []):
        self.address = address
        self.port = port
        self.number_of_columns = number_of_columns
        self.minimum_height = minimum_height
        self.colors = colors
        self.running = True
        self.process = mp.Process(target=self._run)
        self.process.start()

    def _run(self):
        try:
            # Create Monitor instance in the child process
            self.monitor = MonitorUI(self.number_of_columns,
                                     self.minimum_height, self.colors)

            # Create ZMQ context and socket in the child process
            self.context = zmq.Context()
            self.socket = self.context.socket(zmq.REP)
            self.socket.bind(f"tcp://{self.address}:{self.port}")

            while self.running:
                try:
                    message = self.socket.recv_pyobj()
                    cmd, data = message
                    if cmd == 'ROLL':
                        self.monitor.roll()
                    elif cmd == 'PN':
                        self.monitor.set_column_names(*data)
                    elif cmd == 'PD':
                        self.monitor.add_point(*data)
                    elif cmd == 'PXY':
                        self.monitor.set_plots(data)
                    elif cmd == 'TN':
                        self.monitor.set_trace_column_names(*data)
                    elif cmd == 'TD':
                        self.monitor.add_trace(*data)
                    elif cmd == 'TXY':
                        self.monitor.set_trace_plots(data)
                    self.socket.send_string("OK")
                except Exception as e:
                    self.socket.send_string(f"Error: {str(e)}")
        finally:
            # Clean up resources in child process
            try:
                self.socket.close()
                self.context.term()
            except:
                pass

    def __del__(self):
        self.running = False
        try:
            self.process.terminate()
            self.process.join()
        except:
            pass


# Global monitor instance
_monitor = None


def get_monitor(auto_open: bool = True) -> MonitorUI:
    """
    Get or create a global Monitor instance.

    Args:
        auto_open: If True, create a new Monitor if none exists or if existing one is not running

    Returns:
        Monitor instance
    """
    global _monitor

    if auto_open and (_monitor is None or not _monitor.is_alive()):
        _monitor = MonitorUI()

    return cast(MonitorUI, _monitor)


if __name__ == "__main__":
    # Example usage and testing code
    import time

    import numpy as np

    # Example 1: Using Monitor directly
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

    # Example 2: Using MonitorServer and Monitor
    def run_server():
        server = MonitorServer("127.0.0.1", 5555)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    def run_client():
        client = Monitor("127.0.0.1", 5555)
        time.sleep(1)  # Wait for server to start

        client.set_column_names("index", "H", "S")
        client.set_plots("(index,H);(index,S)")
        client.roll()

        for i in range(100):
            client.add_point(i, np.random.randn(), np.sin(i / 20))
            time.sleep(0.2)

    if len(sys.argv) > 1 and sys.argv[1] == "server":
        run_server()
    elif len(sys.argv) > 1 and sys.argv[1] == "client":
        run_client()
