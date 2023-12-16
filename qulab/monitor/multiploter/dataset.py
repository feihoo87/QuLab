from collections import defaultdict, deque

from .config import Nroll

PAUSE_TIME = 1

Number = int | float | complex


def remove_duplicates(input_list: list[str]) -> list[str]:
    """
    Remove duplicates from a list of strings, keeping the order of the elements.
    """
    return list(dict.fromkeys(input_list))


class Dataset():

    def __init__(self):
        self.column_names = []
        self.box = deque(maxlen=Nroll)
        self.dirty = True

    def clear(self):
        self.box.clear()

    def clear_history(self):
        o = self.box.popleft()
        self.box.clear()
        self.box.appendleft(o)

    def set_column_names(self, column_names: list[str]):
        column_names = remove_duplicates(column_names)
        if column_names != self.column_names:
            self.clear()
        self.column_names = column_names

    def get_data(self, step: int, xname: str,
                 yname: str) -> tuple[list[Number], list[Number]]:
        try:
            b = self.box[step]
        except IndexError:
            return [], []
        return b[xname], b[yname]

    def append(self, dataframe: list[Number] | list[list[Number]]):
        if not dataframe:
            return
        try:
            iter(dataframe[0])  # test if dataframe is a list of list
            self._append_traces(dataframe)
        except TypeError:
            self._append_points(dataframe)

    def roll(self):
        self.box.appendleft(defaultdict(list))

    def _append_points(self, points: list[Number]):
        self.dirty = True
        assert (len(points) == len(
            self.column_names)), (f"-PointDataBox\n"
                                  f"-ap\n"
                                  f"-Length Must be same\n"
                                  f"the column_names : {self.column_names}\n"
                                  f"given data : {points}")
        for name, p in zip(self.column_names, points):
            self.box[0][name].append(p)

    def _append_traces(self, traces: list[list[Number]]):
        self.dirty = True
        assert (len(traces) == len(
            self.column_names)), (f"-TraceDataBox\n"
                                  f"-at\n"
                                  f"-Length Must be same\n"
                                  f"the column_names : {self.column_names}\n"
                                  f"given data : {traces}")
        self.box.appendleft(dict(zip(self.column_names, traces)))
