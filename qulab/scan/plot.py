import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axis import Axis
from matplotlib.colors import LogNorm, Normalize, SymLogNorm
from matplotlib.figure import Figure

from qulab.visualization import autoplot

from .record import Record


def _plot(record: Record):
    axis = {}
    for k, v in record.axis.items():
        if len(v) == 1:
            if v[0] not in axis:
                axis[v[0]] = []
            axis[v[0]].append(k)

    record.keys()
    for key, value in record._items.items():
        pass


def plot1d(record: Record, axis: Axis, fig: Figure):
    pass

def plot2d(record: Record, axis: Axis, fig: Figure):
    pass
