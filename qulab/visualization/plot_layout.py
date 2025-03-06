import functools
import operator

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import cm
from matplotlib.colors import Normalize

layout_example = {
    'qubits': {
        'Q0': {
            'pos': (0, 1)
        },
        'Q1': {
            'pos': (1, 0)
        },
        'Q2': {
            'pos': (0, -1)
        },
        'Q3': {
            'pos': (-1, 0)
        }
    },
    'couplers': {
        'C0': {
            'qubits': ['Q0', 'Q1'],
        },
        'C1': {
            'qubits': ['Q1', 'Q2'],
        },
        'C2': {
            'qubits': ['Q2', 'Q3'],
        },
        'C3': {
            'qubits': ['Q0', 'Q3'],
        }
    }
}


def complete_layout(layout):
    for c in layout['couplers']:
        qubits = layout['couplers'][c]['qubits']
        for q in qubits:
            if q not in layout['qubits']:
                raise ValueError('qubit {} not found'.format(q))
            if 'couplers' not in layout['qubits'][q]:
                layout['qubits'][q]['couplers'] = []
            if c not in layout['qubits'][q]['couplers']:
                layout['qubits'][q]['couplers'].append(c)
    return layout


def get_shared_coupler(layout, q1, q2):
    for c in layout['qubits'][q1]['couplers']:
        if q2 in layout['couplers'][c]['qubits']:
            return c
    return None


def get_neighbours(layout,
                   qubit_or_coupler,
                   distance=1,
                   type='qubit',
                   inrange=False):

    def _qubits(couplers):
        ret = set()
        for c in couplers:
            ret = ret | set(layout['couplers'][c]['qubits'])
        return ret

    def _couplers(qubits):
        ret = set()
        for q in qubits:
            ret = ret | set(layout['qubits'][q]['couplers'])
        return ret

    couplers = []
    neighbors = []

    if qubit_or_coupler in layout['qubits']:
        couplers.append(set(layout['qubits'][qubit_or_coupler]['couplers']))
        neighbors.append(_qubits(couplers[0]) - {qubit_or_coupler})
    elif qubit_or_coupler in layout['couplers']:
        if type == 'coupler':
            distance += 1
        neighbors.append(set(layout['couplers'][qubit_or_coupler]['qubits']))
        couplers.append({qubit_or_coupler})
    else:
        raise ValueError(f'qubit or coupler {qubit_or_coupler!r} not found')
    distance -= 1

    while distance > 0:
        couplers.append(_couplers(neighbors[-1]) - couplers[-1])
        neighbors.append(_qubits(couplers[-1]) - neighbors[-1])
        distance -= 1

    if type == 'qubit':
        if inrange:
            return list(functools.reduce(operator.or_, neighbors, set()))
        else:
            return list(neighbors[-1])
    elif type == 'coupler':
        if inrange:
            if qubit_or_coupler in couplers[0]:
                couplers = couplers[1:]
            return list(functools.reduce(operator.or_, couplers, set()))
        else:
            return list(couplers[-1])
    else:
        raise ValueError("type must be 'qubit' or 'coupler'")


def plot_range(ax,
               path,
               text='',
               color=None,
               text_color='k',
               bounder_color='k',
               lw=0.5,
               fontsize=9):
    x, y = path
    center = x.mean(), y.mean()

    if color:
        ax.fill(x, y, color=color, lw=0)

    if lw is not None and lw > 0:
        ax.plot(np.hstack([x, [x[0]]]),
                np.hstack([y, [y[0]]]),
                color=bounder_color,
                lw=lw)

    if text:
        ax.text(center[0],
                center[1],
                text,
                ha='center',
                va='center',
                color=text_color,
                fontsize=fontsize)


def circle_path(pos, r, n=40):
    x, y = pos
    t = 2 * np.pi * np.linspace(0, 1, n, endpoint=False)
    xx = r * np.cos(t) + x
    yy = r * np.sin(t) + y
    return xx, yy


def circle_link_path(pos1, pos2, r1, r2, width, n=20):
    width = min(2 * max(r1, r2), width)

    x1, y1 = pos1
    x2, y2 = pos2

    phi = np.arctan2(y2 - y1, x2 - x1)

    theta1 = np.arcsin(width / 2 / r1)
    theta2 = np.arcsin(width / 2 / r2)

    t = np.linspace(-theta1, theta1, n) + phi
    xx1 = r1 * np.cos(t) + x1
    yy1 = r1 * np.sin(t) + y1

    t = np.linspace(-theta2, theta2, n) + phi + np.pi
    xx2 = r2 * np.cos(t) + x2
    yy2 = r2 * np.sin(t) + y2

    return np.hstack([xx2[-1], xx1,
                      xx2[:-1]]), np.hstack([yy2[-1], yy1, yy2[:-1]])


def circle_half_directed_link_path(pos1, pos2, r1, r2, width, n=20):
    width = min(max(r1, r2), width)

    x1, y1 = pos1
    x2, y2 = pos2

    phi = np.arctan2(y2 - y1, x2 - x1)

    theta1 = np.arcsin(width / r1)
    theta2 = np.arcsin(width / r2)

    t = np.linspace(0.2 * theta1, theta1, n) + phi
    xx1 = r1 * np.cos(t) + x1
    yy1 = r1 * np.sin(t) + y1

    t = np.linspace(-theta2, -0.2 * theta2, n) + phi + np.pi
    xx2 = r2 * np.cos(t) + x2
    yy2 = r2 * np.sin(t) + y2

    v = (xx2[0] - xx1[-1]) + 1j * (yy2[0] - yy1[-1])
    c = (xx2[0] + xx1[-1]) / 2 + 1j * (yy2[0] + yy1[-1]) / 2

    a = np.array([1 / 6, 1 / 12]) + 1j * np.array([0, 0.4 * width / np.abs(v)])
    a = a * v + c

    return np.hstack([xx2[-1], xx1, a.real,
                      xx2[:-1]]), np.hstack([yy2[-1], yy1, a.imag, yy2[:-1]])


def draw(layout, ax=None, qubit_cbar=True, coupler_cbar=True, origin='upper'):
    if ax is None:
        ax = plt.gca()

    for qubit in layout['qubits'].values():
        pos = qubit['pos']
        if origin == 'upper':
            pos = pos[0], -pos[1]
        path = circle_path(pos, qubit.get('radius', 0.5))
        plot_range(ax,
                   path,
                   qubit.get('text', ''),
                   qubit.get('color', None),
                   lw=qubit.get('lw', 0.5),
                   fontsize=qubit.get('fontsize', 9),
                   text_color=qubit.get('text_color', 'k'),
                   bounder_color=qubit.get('bounder_color', 'k'))

    for coupler in layout['couplers'].values():
        q1, q2 = coupler['qubits']
        pos1 = layout['qubits'][q1]['pos']
        pos2 = layout['qubits'][q2]['pos']
        if origin == 'upper':
            pos1 = pos1[0], -pos1[1]
            pos2 = pos2[0], -pos2[1]
        r1 = layout['qubits'][q1].get('radius', 0.5)
        r2 = layout['qubits'][q2].get('radius', 0.5)
        width = coupler.get('width', 0.5)
        lw = coupler.get('lw', 0.5)

        path = circle_link_path(pos1, pos2, r1, r2, width)
        plot_range(ax,
                   path,
                   coupler.get('text', ''),
                   color=coupler.get('color', None),
                   lw=0,
                   fontsize=coupler.get('fontsize', 9),
                   text_color=coupler.get('text_color', 'k'))
        if lw > 0:
            x, y = circle_link_path(pos1, pos2, r1, r2, width, n=2)
            ax.plot(x[:2],
                    y[:2],
                    lw=lw,
                    color=coupler.get('bounder_color', 'k'))
            ax.plot(x[2:],
                    y[2:],
                    lw=lw,
                    color=coupler.get('bounder_color', 'k'))

    ax.axis('equal')
    ax.set_axis_off()

    if qubit_cbar and layout['__colorbar__']['qubit']['norm'] is not None:
        cbar = plt.colorbar(cm.ScalarMappable(
            norm=layout['__colorbar__']['qubit']['norm'],
            cmap=layout['__colorbar__']['qubit']['cmap']),
                            ax=ax,
                            location='bottom',
                            orientation='horizontal',
                            pad=0.01,
                            shrink=0.5)
        cbar.set_label(layout['__colorbar__']['qubit']['label'])
    if coupler_cbar and layout['__colorbar__']['coupler']['norm'] is not None:
        cbar = plt.colorbar(cm.ScalarMappable(
            norm=layout['__colorbar__']['coupler']['norm'],
            cmap=layout['__colorbar__']['coupler']['cmap']),
                            ax=ax,
                            location='bottom',
                            orientation='horizontal',
                            pad=0.01,
                            shrink=0.5)
        cbar.set_label(layout['__colorbar__']['coupler']['label'])


def get_norm(params, elms, vmin=None, vmax=None):
    data = []
    for elm in elms:
        if elm in params:
            if isinstance(params[elm], (int, float)):
                data.append(params[elm])
            elif 'value' in params[elm] and params[elm]['value'] is not None:
                data.append(params[elm]['value'])
    if data:
        if vmin is None:
            vmin = min(data)
        if vmax is None:
            vmax = max(data)
        return Normalize(vmin=vmin, vmax=vmax)
    else:
        return None


def fill_layout(layout,
                params,
                qubit_size=0.5,
                coupler_size=0.5,
                qubit_fontsize=9,
                coupler_fontsize=9,
                qubit_color=None,
                coupler_color=None,
                qubit_cmap='hot',
                qubit_vmax=None,
                qubit_vmin=None,
                qubit_norm=None,
                coupler_cmap='binary',
                coupler_vmax=None,
                coupler_vmin=None,
                coupler_norm=None,
                bounder_color='k',
                lw=0.5):

    qubit_cmap = plt.get_cmap(qubit_cmap)
    coupler_cmap = plt.get_cmap(coupler_cmap)

    if qubit_norm is None:
        qubit_norm = get_norm(params,
                              layout['qubits'].keys(),
                              vmin=qubit_vmin,
                              vmax=qubit_vmax)
    if coupler_norm is None:
        coupler_norm = get_norm(params,
                                layout['couplers'].keys(),
                                vmin=coupler_vmin,
                                vmax=coupler_vmax)
    layout['__colorbar__'] = {
        'coupler': {
            'cmap': coupler_cmap,
            'norm': coupler_norm,
            'label': ''
        },
        'qubit': {
            'cmap': qubit_cmap,
            'norm': qubit_norm,
            'label': ''
        }
    }

    for qubit in layout['qubits']:
        layout['qubits'][qubit]['radius'] = qubit_size
        layout['qubits'][qubit]['fontsize'] = qubit_fontsize
        if qubit in params:
            layout['qubits'][qubit]['lw'] = 0
            if not isinstance(params[qubit], dict):
                params[qubit] = {'value': params[qubit]}
            if 'color' in params[qubit]:
                layout['qubits'][qubit]['color'] = params[qubit]['color']
            elif 'value' in params[qubit] and params[qubit][
                    'value'] is not None:
                layout['qubits'][qubit]['color'] = qubit_cmap(
                    qubit_norm(params[qubit]['value']))
            else:
                layout['qubits'][qubit]['color'] = qubit_color
                if qubit_color is None:
                    layout['qubits'][qubit]['lw'] = lw
            layout['qubits'][qubit]['radius'] = params[qubit].get(
                'radius', qubit_size)
            layout['qubits'][qubit]['fontsize'] = params[qubit].get(
                'fontsize', qubit_fontsize)
            layout['qubits'][qubit]['text'] = params[qubit].get('text', '')
            layout['qubits'][qubit]['text_color'] = params[qubit].get(
                'text_color', 'k')
        else:
            layout['qubits'][qubit]['color'] = qubit_color
            if qubit_color is None:
                layout['qubits'][qubit]['lw'] = lw
            else:
                layout['qubits'][qubit]['lw'] = 0
            layout['qubits'][qubit]['bounder_color'] = bounder_color

    for coupler in layout['couplers']:
        layout['couplers'][coupler]['width'] = coupler_size
        layout['couplers'][coupler]['fontsize'] = coupler_fontsize
        layout['couplers'][coupler]['bounder_color'] = bounder_color
        if coupler in params:
            layout['couplers'][coupler]['lw'] = 0
            if not isinstance(params[coupler], dict):
                params[coupler] = {'value': params[coupler]}
            if 'color' in params[coupler]:
                layout['couplers'][coupler]['color'] = params[coupler]['color']
            elif 'value' in params[coupler] and params[coupler][
                    'value'] is not None:
                layout['couplers'][coupler]['color'] = coupler_cmap(
                    coupler_norm(params[coupler]['value']))
            else:
                layout['couplers'][coupler]['color'] = coupler_color
                if coupler_color is None:
                    layout['couplers'][coupler]['lw'] = lw
            layout['couplers'][coupler]['width'] = params[coupler].get(
                'width', coupler_size)
            layout['couplers'][coupler]['fontsize'] = params[coupler].get(
                'fontsize', coupler_fontsize)
            layout['couplers'][coupler]['text'] = params[coupler].get(
                'text', '')
            layout['couplers'][coupler]['text_color'] = params[coupler].get(
                'text_color', 'k')
        else:
            layout['couplers'][coupler]['color'] = coupler_color
            if coupler_color is None:
                layout['couplers'][coupler]['lw'] = lw
            else:
                layout['couplers'][coupler]['lw'] = 0
            layout['couplers'][coupler]['bounder_color'] = bounder_color

    return layout
