import functools
import operator
from typing import cast

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import cm
from matplotlib.colors import Normalize

from .rot3d import projection, rot_round

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
                raise ValueError(f'qubit {q} not found')
            if 'couplers' not in layout['qubits'][q]:
                layout['qubits'][q]['couplers'] = []
            if c not in layout['qubits'][q]['couplers']:
                layout['qubits'][q]['couplers'].append(c)
    return layout


def read_xlsx_to_dict(filepath: str,
                      key_col: int = 0,
                      value_col: int = 4,
                      sheet_name: str = 0) -> dict:
    """
    读取 .xlsx 文件，将第 key_col 列和第 value_col 列的值分别作为 key、value，返回一个字典。

    :param filepath: Excel 文件路径
    :param key_col: 用作字典键的列索引（0 表示第一列）
    :param value_col: 用作字典值的列索引（0 表示第一列）
    :param sheet_name: 要读取的 sheet 名称或索引，默认第一个 sheet
    :return: { key: value, ... } 形式的字典
    """
    import pandas as pd

    # 读取整个表格
    # df = pd.read_excel(filepath, sheet_name=sheet_name, header=None)
    df = pd.read_excel(filepath, sheet_name=sheet_name)

    # 提取指定列，生成键值对并返回字典
    keys = df.iloc[:, key_col]
    values = df.iloc[:, value_col]
    return dict(zip(keys, values))


def load_layout_from_xlsx(qubit_info, coupler_info, pad_info):
    """
    从 .xlsx 文件中加载布局信息。

    :param qubit_info: 量子比特信息文件路径
    :param coupler_info: 耦合器信息文件路径
    :param pad_info: 垫片信息文件路径
    :return: 布局信息
    """
    _qubits = {}

    qubit_pad = read_xlsx_to_dict(qubit_info, value_col=4)
    coupler_pad = read_xlsx_to_dict(coupler_info, value_col=3)
    pads = {
        v: k
        for k, v in qubit_pad.items()
    } | {
        v: k
        for k, v in coupler_pad.items()
    }
    pad_info = read_xlsx_to_dict(pad_info, value_col=2)

    lyt = {'qubits': {}, 'couplers': {}, 'feedlines': {}}

    for pad, script in pad_info.items():
        info = eval(script)
        match info['style']:
            case 'Q':
                qubit = pads[pad]
                lyt['qubits'][qubit] = {'pos': info['qb'], 'pad': pad}
                _qubits[info['qb']] = qubit
            case 'C':
                coupler = pads[pad]
                if 'cpl' in info:
                    pos = tuple(info['cpl'])
                else:
                    pos = tuple(info['qb'])
                lyt['couplers'][coupler] = {'qubits': pos, 'pad': pad}
            case 'TL':
                l = info['tl']
                if f"T{l}" in lyt['feedlines']:
                    lyt['feedlines'][f"T{l}"]['pads'].append(pad)
                else:
                    lyt['feedlines'][f"T{l}"] = {'pads': [pad]}

    for coupler in lyt['couplers']:
        qubits = lyt['couplers'][coupler]['qubits']
        lyt['couplers'][coupler]['qubits'] = [_qubits[p] for p in qubits]

    return complete_layout(lyt)


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
        return list(neighbors[-1])
    if type == 'coupler':
        if inrange:
            if qubit_or_coupler in couplers[0]:
                couplers = couplers[1:]
            return list(functools.reduce(operator.or_, couplers, set()))
        return list(couplers[-1])
    raise ValueError("type must be 'qubit' or 'coupler'")


def plot_range(ax,
               path,
               text='',
               color=None,
               text_color='k',
               bounder_color='k',
               rotation=0,
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
                rotation=rotation,
                color=text_color,
                fontsize=fontsize)


def circle_path(pos, r, n=40):
    x, y = pos
    t = 2 * np.pi * np.linspace(0, 1, n, endpoint=False)
    xx = r * np.cos(t) + x
    yy = r * np.sin(t) + y
    return xx, yy


def circle_link_path(pos1, pos2, r1, r2, width, n=2):
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


def project(pos, camera=(0, 0, 100), rotation=None):
    if rotation is None:
        rotation = {
            'axis': (0, 0, 1),
            'angle': 0,
            'center': (0, 0, 0),
        }
    x0, y0, z0 = camera
    if len(pos) == 2:
        x, y, z = [*pos, 0]
    else:
        x, y, z = pos
    x, y, z = rot_round(x, y, z, rotation['axis'], rotation['angle'],
                        rotation['center'])
    x, y, _ = projection(x - x0, y - y0, z, d0=z0)
    return x + x0, y + y0


def _draw_qubit(ax, qubit, pos):
    path = circle_path(pos, qubit.get('radius', 0.5))
    plot_range(ax,
               path,
               qubit.get('text', ''),
               qubit.get('color', None),
               lw=qubit.get('lw', 0.5),
               fontsize=qubit.get('fontsize', 9),
               rotation=qubit.get('text_rotation', 0),
               text_color=qubit.get('text_color', 'k'),
               bounder_color=qubit.get('bounder_color', 'k'))


def _draw_coupler(ax, coupler, layout, q1, q2, pos1, pos2):
    r1 = layout['qubits'][q1].get('radius', 0.5)
    r2 = layout['qubits'][q2].get('radius', 0.5)
    width = coupler.get('width', 0.5)
    lw = coupler.get('lw', 0.5)

    text_rotation = 180 * np.arctan2(pos2[1] - pos1[1],
                                     pos2[0] - pos1[0]) / np.pi
    if text_rotation > 90:
        text_rotation -= 180
    elif text_rotation < -90:
        text_rotation += 180

    path = circle_link_path(pos1, pos2, r1, r2, width)
    plot_range(ax,
               path,
               coupler.get('text', ''),
               color=coupler.get('color', None),
               lw=0,
               fontsize=coupler.get('fontsize', 9),
               rotation=coupler.get('text_rotation', text_rotation),
               text_color=coupler.get('text_color', 'k'))
    if lw > 0:
        x, y = circle_link_path(pos1, pos2, r1, r2, width, n=2)
        ax.plot(x[:2], y[:2], lw=lw, color=coupler.get('bounder_color', 'k'))
        ax.plot(x[2:], y[2:], lw=lw, color=coupler.get('bounder_color', 'k'))


def get_range(layout):
    coods = []
    for q in layout['qubits']:
        pos = layout['qubits'][q]['pos']
        if len(pos) == 2:
            x, y, z = [*pos, 0]
        else:
            x, y, z = pos
        coods.append([x, y, z])
    coods = np.array(coods)

    center = coods.mean(axis=0)
    radius = np.max(np.sqrt(np.sum((coods - center)**2, axis=1)))

    return center, radius


def sorted_by_distance(layout, camera, rotation):
    qubits = []
    camera = np.array(camera)
    for q in layout['qubits']:
        pos = layout['qubits'][q]['pos']
        if len(pos) == 2:
            x, y, z = [*pos, 0]
        else:
            x, y, z = pos
        x, y, z = rot_round(x, y, z, rotation['axis'], rotation['angle'],
                            rotation['center'])
        d = np.sqrt(np.sum((np.array([x, y, z]) - camera)**2))
        qubits.append((d, q))
    qubits = sorted(qubits, key=lambda x: x[0])

    plot_order = []
    for _, q in reversed(qubits):
        for c in layout['qubits'][q]['couplers']:
            if ('C', c) not in plot_order:
                plot_order.append(('C', c))
        plot_order.append(('Q', q))
    return plot_order


def draw(layout,
         ax=None,
         qubit_cbar=True,
         coupler_cbar=True,
         origin='upper',
         camera=None,
         rotation=None):
    """
    Draw a layout with qubits and couplers.

    Parameters
    ----------
    layout: dict
        A dictionary containing the layout of the qubits and couplers.
        The dictionary should have the following structure:
        {
            'qubits': {
                'Q0': {'pos': (x, y), 'radius': r, 'text': 'Q0'},
                ...
            },
            'couplers': {
                'C0': {'qubits': ['Q0', 'Q1'], 'width': w, 'text': 'C0'},
                ...
            }
        }
    ax: matplotlib.axes.Axes
        The axes on which to draw the layout. If None, the current axes will be used.
    qubit_cbar: bool
        Whether to draw a colorbar for the qubits.
    coupler_cbar: bool
        Whether to draw a colorbar for the couplers.
    origin: str
        The origin of the layout. If 'upper', the y-coordinates will be inverted.
    camera: tuple
        The position of the camera in 3D space. Default is (0, 0, 1).
    rotation: dict
        The rotation of the layout. The dictionary should have the following structure:
        {
            'axis': (x, y, z),
            'angle': angle,
            'center': (x, y, z)
        }
        If None, no rotation will be applied.
    """
    if ax is None:
        ax = plt.gca()

    center, radius = get_range(layout)

    if rotation is None:
        rotation = {
            'axis': (0, 0, 1),
            'angle': 0,
        }
    if 'center' not in rotation:
        rotation['center'] = center
    if camera is None:
        camera = (center[0], center[1], center[2] + radius * 5)

    plot_order = sorted_by_distance(layout, camera, rotation)

    if origin == 'upper':
        camera = [camera[0], -camera[1], camera[2]]
    for kind, name in plot_order:
        if kind == 'Q':
            pos = layout['qubits'][name]['pos']
            if origin == 'upper':
                pos = [pos[0], -pos[1], *pos[2:]]
            pos = project(pos, camera, rotation)
            _draw_qubit(ax, layout['qubits'][name], pos)
        elif kind == 'C':
            coupler = layout['couplers'][name]
            q1, q2 = coupler['qubits']
            pos1 = layout['qubits'][q1]['pos']
            pos2 = layout['qubits'][q2]['pos']
            if origin == 'upper':
                pos1 = [pos1[0], -pos1[1], *pos1[2:]]
                pos2 = [pos2[0], -pos2[1], *pos2[2:]]
            pos1 = project(pos1, camera, rotation)
            pos2 = project(pos2, camera, rotation)
            _draw_coupler(ax, coupler, layout, q1, q2, pos1, pos2)
        else:
            pass

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
        qubit_norm = cast(
            Normalize,
            get_norm(params,
                     layout['qubits'].keys(),
                     vmin=qubit_vmin,
                     vmax=qubit_vmax))
    if coupler_norm is None:
        coupler_norm = cast(
            Normalize,
            get_norm(params,
                     layout['couplers'].keys(),
                     vmin=coupler_vmin,
                     vmax=coupler_vmax))
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
