"""
This module provides the visualization of the qdat file.
"""
import logging
import math
import re
from functools import reduce

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import cm

log = logging.getLogger(__name__)


def draw(record_dict, fig=None, transpose=True, remove=True):
    """Draw a 2D or 3D plot from a record dict.

    Args:
        record_dict (dict): The record dict.
        fig (matplotlib.figure.Figure): The figure to draw on.
        transpose (bool): Whether to transpose the data.
    """
    dim = record_dict['info']['dim']
    zshape = record_dict['info']['zshape']
    zsize = reduce(lambda a, b: a * b, zshape, 1)

    axis_label = np.asarray(record_dict['info'].get('axis_label',
                                                    [])).flatten()
    z_label = np.asarray(record_dict['info'].get('z_label', [])).flatten()
    axis_unit = np.asarray(record_dict['info'].get('axis_unit', [])).flatten()
    z_unit = np.asarray(record_dict['info'].get('z_unit', [])).flatten()

    fig = plt.figure() if fig is None else fig
    if zsize < 4:
        plot_shape = (1, zsize)
    else:
        n = int(np.sqrt(zsize))
        plot_shape = (math.ceil(zsize / n), n)
    if dim < 3 and zsize < 100:
        figsize = plot_shape[1] * 8, plot_shape[0] * 6
        fig.set_size_inches(*figsize)
        axes = fig.subplots(*plot_shape)
        axes = np.array(axes).flatten()
    else:
        axes = []

    cb_list = []
    if dim == 1 and zsize < 101:
        for i in range(zsize):
            title = record_dict[
                'name'] + f' {i}' if zsize > 1 else record_dict['name']
            try:
                xlabel = axis_label[0]
                ylabel = z_label[0] if len(z_label) == 1 else z_label[i]
            except:
                xlabel, ylabel = 'X', 'Y'
            try:
                x_unit = axis_unit[0]
                y_unit = z_unit[0] if len(z_unit) == 1 else z_unit[i]
            except:
                x_unit, y_unit = 'a.u.', 'a.u.'
            axes[i].set_title(title)
            axes[i].set_xlabel(f'{xlabel} ({x_unit})')
            axes[i].set_ylabel(f'{ylabel} ({y_unit})')
    elif dim == 2 and zsize < 101:
        for i in range(zsize):
            smp = cm.ScalarMappable(norm=None, cmap=None)
            cb = fig.colorbar(smp, ax=axes[i])  # 默认色谱的colorbar
            cb_list.append(cb)
            try:
                title = record_dict['name'] + \
                    f': {z_label[i]}' if zsize > 1 else record_dict['name']
            except:
                title = record_dict[
                    'name'] + f' {i}' if zsize > 1 else record_dict['name']
            try:
                xlabel, ylabel = axis_label[1], axis_label[0]
                if transpose:
                    xlabel, ylabel = ylabel, xlabel
            except:
                xlabel, ylabel = 'X', 'Y'
            try:
                x_unit, y_unit = axis_unit[1], axis_unit[0]
                if transpose:
                    x_unit, y_unit = y_unit, x_unit
            except:
                x_unit, y_unit = 'a.u.', 'a.u.'
            axes[i].set_title(title)
            axes[i].set_xlabel(f'{xlabel} ({x_unit})')
            axes[i].set_ylabel(f'{ylabel} ({y_unit})')
    else:
        message1 = f'dim {dim} is too large (>2)! ' if dim > 2 else f'dim={dim}; '
        message2 = f'zsize {zsize} is too large (>101)!' if zsize > 101 else f'zsize={zsize}'
        log.warning('PASS: ' + message1 + message2)
    #########################################################################################
    try:
        tags = [
            tag.strip(r'\*')
            for tag in record_dict['ParaSpace'].get('tags', [])
            if re.match(r'\*', tag)
        ]
        tag_text = ','.join(tags)
        if tag_text:
            axes[0].text(-0.1,
                         1.1,
                         'TAG: ' + tag_text,
                         horizontalalignment='left',
                         verticalalignment='bottom',
                         transform=axes[0].transAxes)  # fig.transFigure)#
    except:
        pass
    #########################################################################################
    fig.tight_layout()

    dim = record_dict['info']['dim']
    zshape = record_dict['info']['zshape']
    datashape = record_dict['info']['datashape']
    zsize = reduce(lambda a, b: a * b, zshape, 1)
    datashape_r = (*datashape[:dim], zsize)

    if dim == 1 and zsize < 101:
        x, z = record_dict['data']
        z = z.reshape(datashape_r)
        z = np.abs(z) if np.any(np.iscomplex(z)) else z.real
        for i in range(zsize):
            _ = [a.remove() for a in axes[i].get_lines()] if remove else []
            axes[i].plot(x, z[:, i], 'C0')
            axes[i].plot(x, z[:, i], 'C0.')
    elif dim == 2 and zsize < 101:
        x, y, z = record_dict['data']
        x_step, y_step = x[1] - x[0], y[1] - y[0]
        if transpose:
            x, y = y, x
            x_step, y_step = y_step, x_step
        z = z.reshape(datashape_r)
        z = np.abs(z) if np.any(np.iscomplex(z)) else z.real
        for i in range(zsize):
            _z = z[:, :, i]
            _ = [a.remove() for a in axes[i].get_images()] if remove else []
            if transpose:
                _z = _z.T
            im = axes[i].imshow(_z,
                                extent=(y[0] - y_step / 2, y[-1] + y_step / 2,
                                        x[0] - x_step / 2, x[-1] + x_step / 2),
                                origin='lower',
                                aspect='auto')
            cb_list[i].update_normal(im)  # 更新对应的colorbar
    else:
        pass

    return fig, axes
