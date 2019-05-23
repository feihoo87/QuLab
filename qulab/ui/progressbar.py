import asyncio
from collections import deque
from datetime import timedelta
from math import ceil

try:
    from time import monotonic
except ImportError:
    from time import time as monotonic

try:
    import ipywidgets as widgets
    from IPython.display import display
except:
    pass


class ProgressBar:
    sma_window = 10  # Simple Moving Average window

    def __init__(self, *, max=10, description='Progressing', loop=None):
        self.start_ts = monotonic()
        self.avg = 0
        self._avg_update_ts = self.start_ts
        self._ts = self.start_ts
        self._xput = deque(maxlen=self.sma_window)
        self._ProgressWidget = widgets.IntProgress(value=0,
                                                   min=0,
                                                   max=max,
                                                   step=1,
                                                   description=description,
                                                   bar_style='')
        self._elapsedTimeLabel = widgets.Label(value='Used time: 00:00:00')
        self._etaTimeLabel = widgets.Label(value='Remaining time: --:--:--')
        self.ui = widgets.HBox(
            [self._ProgressWidget, self._elapsedTimeLabel, self._etaTimeLabel])
        self.loop = asyncio.get_event_loop() if loop is None else loop
        self._update_loop = None
        self._displayed = False

    @property
    def description(self):
        return self._ProgressWidget.description

    @description.setter
    def description(self, value):
        self._ProgressWidget.description = value

    @property
    def max(self):
        return self._ProgressWidget.max

    @max.setter
    def max(self, value):
        self._ProgressWidget.max = value

    @property
    def index(self):
        return self._ProgressWidget.value

    @index.setter
    def index(self, value):
        self._ProgressWidget.value = value

    @property
    def eta(self):
        return int(
            ceil(self.avg * self.remaining -
                 (monotonic() - self._avg_update_ts)))

    @property
    def eta_td(self):
        return timedelta(seconds=self.eta)

    @property
    def percent(self):
        return self.progress * 100

    @property
    def progress(self):
        return min(1, self.index / self.max)

    @property
    def remaining(self):
        return max(self.max - self.index, 0)

    @property
    def elapsed(self):
        return int(monotonic() - self.start_ts)

    @property
    def elapsed_td(self):
        return timedelta(seconds=self.elapsed)

    def update_avg(self, n, dt):
        if n > 0:
            xput_len = len(self._xput)
            self._xput.append(dt / n)
            now = monotonic()
            if (xput_len < self.sma_window or now - self._avg_update_ts > 1):
                self.avg = sum(self._xput) / len(self._xput)
                self._avg_update_ts = now

    def next(self, n=1):
        now = monotonic()
        dt = now - self._ts
        self.update_avg(n, dt)
        self._ts = now
        self.index = self.index + n
        self.update()

    def goto(self, index):
        incr = index - self.index
        self.next(incr)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.finish(True)
        else:
            self.finish(False)

    def iter(self, it):
        try:
            self.max = len(it)
        except TypeError:
            pass

        with self:
            for x in it:
                yield x
                self.next()

    def display(self):
        if self._displayed:
            return
        display(self.ui)
        self._displayed = True

    def start(self):
        self.display()
        self._ProgressWidget.bar_style = ''
        self.index = 0
        self.start_ts = monotonic()
        self.avg = 0
        self._avg_update_ts = self.start_ts
        self._ts = self.start_ts
        self.update_regularly()

    def update_regularly(self, frequency=1):
        self.update()
        self._update_loop = self.loop.call_later(frequency,
                                                 self.update_regularly)

    def update(self):
        self._elapsedTimeLabel.value = f'Used time: {self.elapsed_td}'
        if self._avg_update_ts == self.start_ts:
            self._etaTimeLabel.value = f'Remaining time: --:--:--'
        else:
            self._etaTimeLabel.value = f'Remaining time: {self.eta_td}'

    def finish(self, success=True):
        if success:
            self._ProgressWidget.bar_style = 'success'
            self._ProgressWidget.value = self._ProgressWidget.max
        else:
            self._ProgressWidget.bar_style = 'danger'
        try:
            self._update_loop.cancel()
        except:
            pass
