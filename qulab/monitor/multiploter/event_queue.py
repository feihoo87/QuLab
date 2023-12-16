import warnings
from multiprocessing import Queue

from .dataset import Dataset
from .toolbar import ToolBar


class EventQueue():

    def __init__(self, queue: Queue, toolbar: ToolBar, point_dataset: Dataset,
                 trace_dataset: Dataset):
        self.toolbar = toolbar
        self.queue = queue
        self.point_dataset = point_dataset
        self.trace_dataset = trace_dataset

    def flush(self):
        while (not self.queue.empty()):
            words = self.queue.get()
            try:
                assert (isinstance(
                    words, tuple)), "QueueHandler - fifo Content must be tuple"
                assert (
                    len(words) == 2
                ), "QueueHandler -the tuple must be like (\"command_type\" , \"DATA\")"
                cmd, data = words
                assert (isinstance(
                    cmd, str)), "QueueHandler - the command should be a string"
            except AssertionError as e:
                warnings.warn(e.args[0])
                continue

            self.handle(cmd, data)

    def handle(self, cmd, data):
        match cmd:
            case "PN":
                self.point_dataset.set_column_names(data)
                self.toolbar.refresh_comb()
            case "TN":
                self.trace_dataset.set_column_names(data)
                self.toolbar.refresh_comb()
            case "PD":
                self.point_dataset.append(data)
            case "TD":
                self.trace_dataset.append(data)
            case "ROLL":
                self.point_dataset.roll()
            case "PXY":
                self.toolbar.set_point_text(data)
            case "TXY":
                self.toolbar.set_trace_text(data)
            case _:
                warnings.warn(f"QueueHandler - unknown command : {cmd}")
