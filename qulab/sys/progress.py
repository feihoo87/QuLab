import asyncio
from collections import deque
from datetime import timedelta
from time import monotonic

from blinker import Signal

try:
    import ipywidgets as widgets
    from IPython.display import display
except:
    pass


class Progress:
    sma_window = 10  # Simple Moving Average window

    def __init__(self, *, max=10):
        self.start_ts = monotonic()
        self._ts = self.start_ts
        self._xput = deque(maxlen=self.sma_window)
        self._max = max
        self.index = 0
        self.updated = Signal()
        self.finished = Signal()
        self.status = "running"

    @property
    def progress(self):
        return min(1.0, self.index / self.max)

    @property
    def remaining(self):
        return max(self.max - self.index, 0)

    @property
    def percent(self):
        return self.progress * 100

    @property
    def elapsed(self):
        if self.status != "running":
            return self._ts - self.start_ts
        return monotonic() - self.start_ts

    @property
    def eta(self):
        if self.status != "running":
            return 0
        avg = sum(self._xput) / len(self._xput)
        dt = monotonic() - self._ts
        if dt > avg:
            avg = 0.9 * avg + 0.1 * dt
            return avg * self.remaining
        else:
            return avg * self.remaining - dt

    @property
    def max(self):
        return self._max

    @max.setter
    def max(self, x):
        self._max = x
        self.updated.send(self)

    def next(self, n=1):
        assert n > 0
        now = monotonic()
        dt = now - self._ts
        self._xput.append(dt / n)
        self._ts = now
        self.index = self.index + n
        self.updated.send(self)

    def goto(self, index):
        incr = index - self.index
        self.next(incr)

    def finish(self, success=True):
        self._ts = monotonic()
        if success:
            self.status = "finished"
        else:
            self.status = "failure"
        self.finished.send(self, success=success)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.finish(True)
        else:
            self.finish(False)

    def iter(self, it, max=None):
        if max is None:
            try:
                self.max = len(it)
            except TypeError:
                self.max = 0
        else:
            self.max = max

        with self:
            for x in it:
                yield x
                self.next()

    def __repr__(self):
        if self._ts == self.start_ts:
            eta_td = '--:--:--'
        else:
            eta_td = timedelta(seconds=round(self.eta))
        return (
            f"({self.index}/{self.max}) {self.percent:.0f}%"
            f" Used time: {timedelta(seconds=round(self.elapsed))} Remaining time: {eta_td}"
            f" {self.status}")


class ProgressBar():

    def listen(self, progress: Progress):
        self.progress = progress
        self.progress.updated.connect(self.update)
        self.progress.finished.connect(self.finish)

    def update(self, sender: Progress):
        raise NotImplementedError()

    def finish(self, sender: Progress, success: bool):
        self.progress.updated.disconnect(self.update)
        self.progress.finished.disconnect(self.finish)


class JupyterProgressBar(ProgressBar):

    def __init__(self, *, description='Progressing', hiden=False):
        self.description = description
        self.hiden = hiden

    def display(self):
        if self.hiden:
            return
        self.progress_ui = widgets.FloatProgress(value=0,
                                                 min=0,
                                                 max=100.0,
                                                 step=1,
                                                 description=self.description,
                                                 bar_style='')

        self.elapsed_ui = widgets.Label(value='Used time: 00:00:00')
        self.eta_ui = widgets.Label(value='Remaining time: --:--:--')
        self.ui = widgets.HBox(
            [self.progress_ui, self.elapsed_ui, self.eta_ui])
        display(self.ui)

    def listen(self, progress: Progress):
        super().listen(progress)
        self.update_regularly()

    def update_regularly(self, frequency=1):
        try:
            self.update(self.progress)
        except:
            pass
        asyncio.get_running_loop().call_later(frequency, self.update_regularly)

    def update(self, sender: Progress):
        if self.hiden:
            return
        self.progress_ui.value = sender.percent
        self.elapsed_ui.value = (
            f'({sender.index}/{sender.max}) '
            f'Used time: {timedelta(seconds=round(sender.elapsed))}')
        if sender.eta == sender.start_ts:
            self.eta_ui.value = f'Remaining time: --:--:--'
        else:
            self.eta_ui.value = f'Remaining time: {timedelta(seconds=round(sender.eta))}'

    def finish(self, sender: Progress, success: bool = True):
        if self.hiden:
            return
        if success:
            self.progress_ui.bar_style = 'success'
            self.progress_ui.value = 100.0
        else:
            self.progress_ui.bar_style = 'danger'
        super().finish(sender, success)
