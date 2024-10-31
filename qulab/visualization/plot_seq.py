import itertools

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import PathPatch
from matplotlib.path import Path


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


def make_path(fx, fy, dfx, dfy, t):

    def p(fx, fy, dfx, dfy, t0, t1):
        x1, x2 = fx(t0), fx(t1)
        y1, y2 = fy(t0), fy(t1)
        dx1, dx2 = dfx(t0), dfx(t1)
        dy1, dy2 = dfy(t0), dfy(t1)

        xp = (dy1 * dx2 * x1 - dy2 * dx1 * x2 - dx1 * dx2 *
              (y1 - y2)) / (dy1 * dx2 - dy2 * dx1)

        yp = (dy1 * dx2 * y2 - dy2 * dx1 * y1 + dy1 * dy2 *
              (x1 - x2)) / (dy1 * dx2 - dy2 * dx1)

        return xp, yp

    path = [(fx(t[0]), fy(t[0]))]
    codes = [Path.MOVETO]

    for i in range(1, len(t)):
        x, y = p(fx, fy, dfx, dfy, t[i - 1], t[i])
        path.append((x, y))
        codes.append(Path.CURVE3)
        path.append((fx(t[i]), fy(t[i])))
        codes.append(Path.CURVE3)
    return path, codes


def plot_square(ax,
                x=0,
                y=0,
                width=1,
                hight=1,
                r=0.2,
                ls='-',
                lw=2,
                fc='none',
                ec='black'):

    path = np.array([(0, 1), (1 - 2 * r, 1), (1, 1), (1, 1 - 2 * r),
                     (1, -1 + 2 * r), (1, -1), (1 - 2 * r, -1),
                     (-1 + 2 * r, -1), (-1, -1), (-1, -1 + 2 * r),
                     (-1, 1 - 2 * r), (-1, 1), (-1 + 2 * r, 1), (0, 1)])
    path[:, 0] = path[:, 0] * width / 2 + x
    path[:, 1] = path[:, 1] * hight / 2 + y
    codes = [
        Path.MOVETO,
        Path.LINETO,
        Path.CURVE3,
        Path.CURVE3,
        Path.LINETO,
        Path.CURVE3,
        Path.CURVE3,
        Path.LINETO,
        Path.CURVE3,
        Path.CURVE3,
        Path.LINETO,
        Path.CURVE3,
        Path.CURVE3,
        Path.CLOSEPOLY,
    ]
    pp1 = PathPatch(Path(path, codes),
                    ls=ls,
                    lw=lw,
                    fc=fc,
                    ec=ec,
                    transform=ax.transData)

    ax.add_patch(pp1)


def plot_measure(ax,
                 x=0,
                 y=0,
                 size=1,
                 r=0.2,
                 ls='-',
                 lw=2,
                 fc='none',
                 ec='black'):
    width = size
    hight = 0.8 * size
    plot_square(ax, x, y, width, hight, r, ls, lw, fc, ec)

    fx = lambda t: 0.5 * width * np.cos(t) + x
    fy = lambda t: 0.5 * hight * np.sin(t) + y - 0.2 * hight
    dfx = lambda t: -0.5 * width * np.sin(t)
    dfy = lambda t: 0.5 * hight * np.cos(t)
    t = np.linspace(1 / 6, 5 / 6, 5) * np.pi
    path, codes = make_path(fx, fy, dfx, dfy, t)

    pp1 = PathPatch(Path(path, codes),
                    ls=ls,
                    lw=lw,
                    fc=fc,
                    ec=ec,
                    transform=ax.transData)

    ax.add_patch(pp1)

    angle = np.pi / 6

    ax.arrow(x,
             y - 0.25 * width,
             0.55 * width * np.sin(angle),
             0.55 * width * np.cos(angle),
             head_width=0.07 * width,
             head_length=0.1 * width,
             lw=lw,
             color=ec)

    return (x - width / 2, x + width / 2)


def plot_gate(ax,
              x=0,
              y=0,
              size=1,
              text="$U$",
              ls='-',
              lw=2,
              r=0.2,
              fc='none',
              ec='black',
              fontsize=16):
    width = size
    hight = 0.8 * size
    plot_square(ax, x, y, width, hight, r, ls, lw, fc, ec)
    ax.text(x, y, text, ha='center', va='center', color=ec, fontsize=fontsize)

    return (x - width / 2, x + width / 2)


def plot_waveform(ax,
                  wav,
                  offset,
                  gaps=[],
                  ec='black',
                  fc='none',
                  ls='-',
                  lw=2):
    t = np.linspace(wav.start, wav.stop, 1001)
    points = wav(t) + offset
    for a, b in gaps:
        points[(t > a) * (t < b)] = np.nan
    ax.plot(t, points, ls=ls, color=ec, lw=lw)
    if fc != 'none':
        ax.fill_between(t, points, offset, color=fc)
