import numpy as np
from matplotlib.patches import Circle, FancyArrow, PathPatch
from matplotlib.path import Path
from waveforms import *


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
                x=0.0,
                y=0.0,
                width=1.0,
                hight=1.0,
                radius=0.2,
                ls='-',
                lw=2.0,
                fc='none',
                ec='black'):
    r = radius
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

    ax.add_artist(pp1)


def plot_measure(ax,
                 x=0,
                 y=0,
                 size=1,
                 ratio=0.8,
                 radius=0.2,
                 ls='-',
                 lw=2,
                 fc='none',
                 ec='black'):
    width = size
    hight = ratio * size
    plot_square(ax, x, y, width, hight, radius, ls, lw, fc, ec)

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

    ax.add_artist(pp1)

    angle = np.pi / 6

    arr = FancyArrow(x,
                     y - 0.25 * width,
                     0.55 * width * np.sin(angle),
                     0.55 * width * np.cos(angle),
                     head_length=0.1 * width,
                     head_width=0.07 * width,
                     lw=lw,
                     color=ec)

    ax.add_artist(arr)

    return (x - width / 2, x + width / 2)


def plot_cnot(ax, x=0, ctr=1, tgt=0, size=0.5, lw=2, fc='none', ec='k'):
    c = Circle((x, tgt), radius=size / 2, lw=lw, fc=fc, ec=ec)
    ax.add_artist(c)

    c = Circle((x, ctr), radius=0.1 * size, lw=lw, fc=ec, ec=ec)
    ax.add_artist(c)

    path, codes = [(x - size / 2, tgt), (
        x + size / 2,
        tgt,
    )], [Path.MOVETO, Path.LINETO]

    p = PathPatch(Path(path, codes),
                  ls='-',
                  lw=lw,
                  ec=ec,
                  transform=ax.transData)
    ax.add_artist(p)

    if ctr > tgt:
        up, down = ctr, tgt - size / 2
    else:
        up, down = tgt + size / 2, ctr
    path, codes = [(x, up), (x, down)], [Path.MOVETO, Path.LINETO]

    p = PathPatch(Path(path, codes),
                  ls='-',
                  lw=lw,
                  ec=ec,
                  transform=ax.transData)
    ax.add_artist(p)

    return (x - 0.1 * size, x + 0.1 * size), (x - 0.5 * size, x + 0.5 * size)


def plot_cz(ax, x=0, ctr=1, tgt=0, size=0.5, lw=2, fc='none', ec='k'):
    c = Circle((x, ctr), radius=0.1 * size, lw=lw, fc=ec, ec=ec)
    ax.add_artist(c)

    c = Circle((x, tgt), radius=0.1 * size, lw=lw, fc=ec, ec=ec)
    ax.add_artist(c)

    path, codes = [(x, ctr), (x, tgt)], [Path.MOVETO, Path.LINETO]

    p = PathPatch(Path(path, codes),
                  ls='-',
                  lw=lw,
                  ec=ec,
                  transform=ax.transData)
    ax.add_artist(p)

    return (x - 0.1 * size, x + 0.1 * size), (x - 0.1 * size, x + 0.1 * size)


def plot_iswap(ax, x=0, ctr=1, tgt=0, size=0.2, lw=2, fc='none', ec='k'):
    path, codes = [(x - size / 2, ctr - size / 2),
                   (x + size / 2, ctr + size / 2)], [Path.MOVETO, Path.LINETO]
    p = PathPatch(Path(path, codes),
                  ls='-',
                  lw=lw,
                  ec=ec,
                  transform=ax.transData)
    ax.add_artist(p)

    path, codes = [(x - size / 2, ctr + size / 2),
                   (x + size / 2, ctr - size / 2)], [Path.MOVETO, Path.LINETO]
    p = PathPatch(Path(path, codes),
                  ls='-',
                  lw=lw,
                  ec=ec,
                  transform=ax.transData)
    ax.add_artist(p)

    path, codes = [(x - size / 2, tgt - size / 2),
                   (x + size / 2, tgt + size / 2)], [Path.MOVETO, Path.LINETO]
    p = PathPatch(Path(path, codes),
                  ls='-',
                  lw=lw,
                  ec=ec,
                  transform=ax.transData)
    ax.add_artist(p)

    path, codes = [(x - size / 2, tgt + size / 2),
                   (x + size / 2, tgt - size / 2)], [Path.MOVETO, Path.LINETO]
    p = PathPatch(Path(path, codes),
                  ls='-',
                  lw=lw,
                  ec=ec,
                  transform=ax.transData)
    ax.add_artist(p)

    path, codes = [(x, ctr), (x, tgt)], [Path.MOVETO, Path.LINETO]
    p = PathPatch(Path(path, codes),
                  ls='-',
                  lw=lw,
                  ec=ec,
                  transform=ax.transData)
    ax.add_artist(p)

    return (x, x), (x, x)


def plot_gate(ax,
              x=0,
              y=0,
              size=1,
              ratio=0.8,
              radius=0.2,
              text="$U$",
              ls='-',
              lw=2,
              fc='none',
              ec='black',
              fontsize=16):
    width = size
    hight = ratio * size
    plot_square(ax,
                x,
                y,
                width,
                hight,
                radius=radius,
                ls=ls,
                lw=lw,
                fc=fc,
                ec=ec)
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


def _max_ticks(table, *qubits):
    ticks = []
    for q in qubits:
        ticks.append(len(table.get(q, [])))
    return max(ticks)


def _extend_table(table, q, ticks):
    table[q] = table.get(q, []) + [None] * (ticks - len(table.get(q, [])))


def _barrier(table, *qubits):
    ticks = _max_ticks(table, *qubits)
    for q in qubits:
        _extend_table(table, q, ticks)


def qlisp_to_table(circ):
    table = {}
    for gate, *qubits in circ:
        _barrier(table, *qubits)
        if isinstance(gate, str) and gate == 'Barrier':
            continue
        for q in qubits:
            table[q].append((gate, *qubits))
    _barrier(table, *table.keys())
    return table


def table_to_layers(table):
    layers = []
    for q, gates in table.items():
        for i, gate in enumerate(gates):
            if len(layers) <= i:
                layers.append({})
            layers[i][q] = gate
    return layers


def _plot_layer(ax, layer, qubit_mapping=None):
    gaps = {}
    if qubit_mapping is None:
        qubit_mapping = sorted(layer.keys())
    return gaps


def plot_qlisp(ax, circ, qubit_mapping=None):
    layers = table_to_layers(qlisp_to_table(circ))
