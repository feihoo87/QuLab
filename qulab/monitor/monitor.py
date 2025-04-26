import multiprocessing as mp
import sys

# try:
#     mp.set_start_method("spawn")
# except:
#     pass


def main(queue: mp.Queue,
         ncols: int = 4,
         minimum_height: int = 400,
         colors: list[tuple[int, int, int]] = []):
    from .mainwindow import MainWindow
    from .qt_compat import QtWidgets

    app = QtWidgets.QApplication(sys.argv)
    main = MainWindow(queue, ncols, minimum_height, colors)
    sys.exit(app.exec())


class Monitor():

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

    def start(self):
        if self.process is not None and self.process.is_alive():
            return
        self.queue = mp.Queue(20)
        self.process = mp.Process(target=main,
                                  args=(self.queue, self.number_of_columns,
                                        self.minimum_height, self.colors))
        self.process.start()

    def _put(self, w: tuple):
        self.queue.put(w)

    def roll(self):
        self._put(("ROLL", None))

    def set_column_names(self, *arg):
        self._put(('PN', list(arg)))

    def add_point(self, *arg):
        self._put(('PD', list(arg)))

    def set_plots(self, arg):
        """
        arg: str, like "(x,y)" or "(x1,y1);(x2,y2);"
        """
        self._put(('PXY', str(arg)))

    def set_trace_column_names(self, *arg):
        self._put(('TN', list(arg)))

    def add_trace(self, *arg):
        self._put(('TD', list(arg)))

    def set_trace_plots(self, arg):
        """
        arg: str, like "(x,y)" or "(x1,y1);(x2,y2);"
        """
        self._put(('TXY', str(arg)))

    def __del__(self):
        try:
            self.process.kill()
        except:
            pass

    def is_alive(self):
        return self.process.is_alive()


_monitor = None


def get_monitor(auto_open=True):
    global _monitor

    if auto_open and (_monitor is None or not _monitor.is_alive()):
        _monitor = Monitor()

    return _monitor


if __name__ == "__main__":
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
