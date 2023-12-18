import itertools

import matplotlib.pyplot as plt
import numpy as np


def cycle(x0, y0, r, a=0, b=2 * np.pi):
    t = np.linspace(a, b, 101)
    x = r * np.cos(t) + x0
    y = r * np.sin(t) + y0
    return x, y


def plotSquare(xc, yc, xs, ys, radius=0, color='C0', ax=None):
    ax = plt.gca() if ax is None else ax

    l, r, b, u = xc - xs / 2, xc + xs / 2, yc - ys / 2, yc + ys / 2
    x = np.linspace(l + radius, r - radius, 2)
    y = np.linspace(b + radius, u - radius, 2)

    ax.plot(x, [u, u], color=color)
    ax.plot(x, [b, b], color=color)
    ax.plot([l, l], y, color=color)
    ax.plot([r, r], y, color=color)

    xx, yy = cycle(x[-1], y[-1], radius, 0, np.pi / 2)
    ax.plot(xx, yy, color=color)

    xx, yy = cycle(x[0], y[-1], radius, np.pi / 2, np.pi)
    ax.plot(xx, yy, color=color)

    xx, yy = cycle(x[0], y[0], radius, np.pi, np.pi * 3 / 2)
    ax.plot(xx, yy, color=color)

    xx, yy = cycle(x[-1], y[0], radius, np.pi * 3 / 2, np.pi * 2)
    ax.plot(xx, yy, color=color)


def plotMesure(x0=0, y0=0, size=1, color='C0', ax=None):

    ax = plt.gca() if ax is None else ax

    x, y = cycle(x0, y0 - 0.37 * size, 0.57 * size, np.pi / 4, np.pi * 3 / 4)
    ax.plot(x, y, color=color)

    plotSquare(x0, y0, size, 0.8 * size, radius=0.2 * size, color=color, ax=ax)

    angle = np.pi / 6

    ax.arrow(x0,
             y0 - 0.25 * size,
             0.55 * size * np.sin(angle),
             0.55 * size * np.cos(angle),
             head_width=0.07 * size,
             head_length=0.1 * size,
             color=color)


def plot_seq(ax, waves, measure=[1], gap=4, maxTime=20, xlim=None):
    t = np.linspace(0, maxTime, 1001)
    tt = np.linspace(0, maxTime - gap, 1001)
    styles = ['-', '--', ':', '-.']
    colors = ['C0', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9']
    for i, (wavgroup, color) in enumerate(zip(waves, itertools.cycle(colors))):
        if i in measure:
            time = tt
        else:
            time = t
        if not isinstance(wavgroup, tuple):
            wavgroup = (wavgroup, )

        for wav, style in zip(wavgroup, itertools.cycle(styles)):
            ax.plot(time, wav(time) - gap * i, style, color=color)
            if i in measure:
                plotMesure(maxTime - gap / 2,
                           -gap * i,
                           gap,
                           color='black',
                           ax=ax)

    ax.axis('equal')

    ax.spines['left'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    if xlim is not None:
        ax.set_xlim(xlim)
