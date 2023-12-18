import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm
from matplotlib.ticker import EngFormatter, LogFormatterSciNotation
from scipy.interpolate import griddata


def good_for_logscale(x, threshold=4):
    if np.any(x <= 0):
        return False
    mid = (np.nanmin(x) + np.nanmax(x)) / 2
    a = np.count_nonzero(np.nan_to_num(x <= mid, nan=0))
    b = np.count_nonzero(np.nan_to_num(x >= mid, nan=0))
    if a / b > threshold:
        return True
    return False


def equal_logspace(x):
    logx = np.logspace(np.log10(x[0]), np.log10(x[-1]), len(x))
    return np.allclose(x, logx)


def equal_linspace(x):
    linearx = np.linspace(x[0], x[-1], len(x))
    return np.allclose(x, linearx)


def as_1d_data(x, y, z):
    x = np.asarray(x)
    y = np.asarray(y)
    z = np.asarray(z)
    if z.ndim == 1:
        return x, y, z

    if z.ndim == 2:
        x, y = np.meshgrid(x, y)
        return x.ravel(), y.ravel(), z.ravel()

    raise ValueError("z must be 1D or 2D")


def griddata_logx_logy(x, y, z, shape=(401, 401)):
    x, y, z = as_1d_data(x, y, z)
    xspace = np.logspace(np.log10(x.min()), np.log10(x.max()), shape[0])
    yspace = np.logspace(np.log10(y.min()), np.log10(y.max()), shape[1])
    xgrid, ygrid = np.meshgrid(xspace, yspace)
    zgrid = griddata((x, y), z, (xgrid, ygrid), method='nearest')
    return xspace, yspace, zgrid


def griddata_logx_linear_y(x, y, z, shape=(401, 401)):
    x, y, z = as_1d_data(x, y, z)
    xspace = np.logspace(np.log10(x.min()), np.log10(x.max()), shape[0])
    yspace = np.linspace(y.min(), y.max(), shape[1])
    xgrid, ygrid = np.meshgrid(xspace, yspace)
    zgrid = griddata((x, y), z, (xgrid, ygrid), method='nearest')
    return xspace, yspace, zgrid


def griddata_linear_x_logy(x, y, z, shape=(401, 401)):
    x, y, z = as_1d_data(x, y, z)
    xspace = np.linspace(x.min(), x.max(), shape[0])
    yspace = np.logspace(np.log10(y.min()), np.log10(y.max()), shape[1])
    xgrid, ygrid = np.meshgrid(xspace, yspace)
    zgrid = griddata((x, y), z, (xgrid, ygrid), method='nearest')
    return xspace, yspace, zgrid


def griddata_linear_x_linear_y(x, y, z, shape=(401, 401)):
    x, y, z = as_1d_data(x, y, z)
    xspace = np.linspace(x.min(), x.max(), shape[0])
    yspace = np.linspace(y.min(), y.max(), shape[1])
    xgrid, ygrid = np.meshgrid(xspace, yspace)
    zgrid = griddata((x, y), z, (xgrid, ygrid), method='nearest')
    return xspace, yspace, zgrid


def _get_log_ticks(x):
    log10x = np.log10(x)

    major_ticks = np.array(
        range(math.floor(log10x[0]) - 1,
              math.ceil(log10x[-1]) + 1))
    minor_ticks = np.hstack([
        np.log10(np.linspace(2, 10, 9, endpoint=False)) + x
        for x in major_ticks
    ])

    major_ticks = major_ticks[(major_ticks >= log10x[0]) *
                              (major_ticks <= log10x[-1])]
    minor_ticks = minor_ticks[(minor_ticks >= log10x[0]) *
                              (minor_ticks <= log10x[-1])]

    return log10x, major_ticks, minor_ticks


class MyLogFormatter(EngFormatter):

    def format_ticks(self, values):
        if self.unit is None or self.unit == '':
            fmt = LogFormatterSciNotation()
            return [f"${fmt.format_data(10.0**x)}$" for x in values]
        else:
            return super().format_ticks(values)

    def format_eng(self, x):
        if self.unit is None or self.unit == '':
            self.unit = ''
            return f"{10.0**x:g}"
        else:
            return super().format_eng(10.0**x)


def imshow_logx(x, y, z, x_unit=None, ax=None, **kwargs):
    if ax is None:
        ax = plt.gca()

    log10x, major_ticks, minor_ticks = _get_log_ticks(x)

    dlogx, dy = log10x[1] - log10x[0], y[1] - y[0]
    extent = (log10x[0] - dlogx / 2, log10x[-1] + dlogx / 2, y[0] - dy / 2,
              y[-1] + dy / 2)

    img = ax.imshow(z, extent=extent, **kwargs)

    ax.set_xticks(major_ticks, minor=False)
    ax.xaxis.set_major_formatter(MyLogFormatter(x_unit))
    ax.set_xticks(minor_ticks, minor=True)

    return img


def imshow_logy(x, y, z, y_unit=None, ax=None, **kwargs):
    if ax is None:
        ax = plt.gca()

    log10y, major_ticks, minor_ticks = _get_log_ticks(y)

    dlogy, dx = log10y[1] - log10y[0], x[1] - x[0]
    extent = (x[0] - dx / 2, x[-1] + dx / 2, log10y[0] - dlogy / 2,
              log10y[-1] + dlogy / 2)

    img = ax.imshow(z, extent=extent, **kwargs)

    ax.set_yticks(major_ticks, minor=False)
    ax.yaxis.set_major_formatter(MyLogFormatter(y_unit))
    ax.set_yticks(minor_ticks, minor=True)

    return img


def imshow_loglog(x, y, z, x_unit=None, y_unit=None, ax=None, **kwargs):
    if ax is None:
        ax = plt.gca()

    log10x, x_major_ticks, x_minor_ticks = _get_log_ticks(x)
    log10y, y_major_ticks, y_minor_ticks = _get_log_ticks(y)

    dlogx, dlogy = log10x[1] - log10x[0], log10y[1] - log10y[0]
    extent = (log10x[0] - dlogx / 2, log10x[-1] + dlogx / 2,
              log10y[0] - dlogy / 2, log10y[-1] + dlogy / 2)

    img = ax.imshow(z, extent=extent, **kwargs)

    ax.set_xticks(x_major_ticks, minor=False)
    ax.xaxis.set_major_formatter(MyLogFormatter(x_unit))
    ax.set_xticks(x_minor_ticks, minor=True)

    ax.set_yticks(y_major_ticks, minor=False)
    ax.yaxis.set_major_formatter(MyLogFormatter(y_unit))
    ax.set_yticks(y_minor_ticks, minor=True)

    return img


def plot_lines(x,
               y,
               z,
               xlabel,
               ylabel,
               zlabel,
               x_unit,
               y_unit,
               z_unit,
               ax,
               xscale='linear',
               yscale='linear',
               zscale='linear',
               index=None,
               **kwds):
    z = np.asarray(z)
    if len(y) > len(x):
        x, y = y, x
        xlabel, ylabel = ylabel, xlabel
        xscale, yscale = yscale, xscale
        z = z.T
    if index is not None:
        y = y[index]
        z = z[index, :]

    for i, l in enumerate(y):
        if y_unit:
            label = f"{ylabel}={l:.3} [{y_unit}]"
        else:
            if isinstance(l, float):
                label = f"{ylabel}={l:.3}"
            else:
                label = f"{ylabel}={l}"
        ax.plot(x, z[i, :], label=label, **kwds)
    ax.legend()
    xlabel = f"{xlabel} [{x_unit}]" if x_unit else xlabel
    zlabel = f"{zlabel} [{z_unit}]" if z_unit else zlabel
    ax.set_xlabel(xlabel)
    ax.set_ylabel(zlabel)
    ax.set_xscale(xscale)
    ax.set_yscale(zscale)


def plot_img(x,
             y,
             z,
             xlabel,
             ylabel,
             zlabel,
             x_unit,
             y_unit,
             z_unit,
             fig,
             ax,
             xscale='linear',
             yscale='linear',
             zscale='linear',
             resolution=None,
             **kwds):
    kwds.setdefault('origin', 'lower')
    kwds.setdefault('aspect', 'auto')
    kwds.setdefault('interpolation', 'nearest')

    if zscale == 'log':
        vmim = kwds.get('vmin', np.min(z))
        vmax = kwds.get('vmax', np.max(z))
        kwds.setdefault('norm', LogNorm(vmax=vmax, vmin=vmim))
    zlabel = f"{zlabel} [{z_unit}]" if z_unit else zlabel

    band_area = False
    if x.ndim == 1 and y.ndim == 2 and y.shape[1] == x.shape[0]:
        x = np.asarray([x] * y.shape[0])
        band_area = True
    elif x.ndim == 2 and y.ndim == 1 and x.shape[0] == y.shape[0]:
        y = np.asarray([y] * x.shape[1]).T
        band_area = True
    if band_area:
        kwds.pop('origin', None)
        kwds.pop('aspect', None)
        kwds.pop('interpolation', None)
        pc = ax.pcolormesh(x, y, z, **kwds)
        xlabel = f"{xlabel} [{x_unit}]" if x_unit else xlabel
        ylabel = f"{ylabel} [{y_unit}]" if y_unit else ylabel
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        cb = fig.colorbar(pc, ax=ax)
        ax.set_xscale(xscale)
        ax.set_yscale(yscale)
        cb.set_label(zlabel)
        return

    if resolution is None:
        resolution = (401, 401)
    elif isinstance(resolution, int):
        resolution = (resolution, resolution)

    if (z.ndim == 1 or (xscale == 'linear' and not equal_linspace(x))
            or (yscale == 'linear' and not equal_linspace(y))
            or (xscale == 'log' and not equal_logspace(x))
            or (yscale == 'log' and not equal_logspace(y))):
        griddata = {
            ('log', 'log'): griddata_logx_logy,
            ('log', 'linear'): griddata_logx_linear_y,
            ('linear', 'log'): griddata_linear_x_logy,
            ('linear', 'linear'): griddata_linear_x_linear_y,
        }[(xscale, yscale)]
        x, y, z = griddata(x, y, z, resolution)

    if (xscale, yscale) == ('linear', 'linear'):
        dx, dy = x[1] - x[0], y[1] - y[0]
        extent = (x[0] - dx / 2, x[-1] + dx / 2, y[0] - dy / 2, y[-1] + dy / 2)
        kwds.setdefault('extent', extent)
        img = ax.imshow(np.asarray(z), **kwds)
        xlabel = f"{xlabel} [{x_unit}]" if x_unit else xlabel
        ylabel = f"{ylabel} [{y_unit}]" if y_unit else ylabel
    elif (xscale, yscale) == ('log', 'linear'):
        ylabel = f"{ylabel} [{y_unit}]" if y_unit else ylabel
        img = imshow_logx(x, y, z, x_unit, ax, **kwds)
    elif (xscale, yscale) == ('linear', 'log'):
        xlabel = f"{xlabel} [{x_unit}]" if x_unit else xlabel
        img = imshow_logy(x, y, z, y_unit, ax, **kwds)
    elif (xscale, yscale) == ('log', 'log'):
        img = imshow_loglog(x, y, z, x_unit, y_unit, ax, **kwds)
    else:
        pass
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    cb = fig.colorbar(img, ax=ax)
    cb.set_label(zlabel)


def plot_scatter(x,
                 y,
                 z,
                 xlabel,
                 ylabel,
                 zlabel,
                 x_unit,
                 y_unit,
                 z_unit,
                 fig,
                 ax,
                 xscale='linear',
                 yscale='linear',
                 zscale='linear',
                 **kwds):
    if np.any(np.iscomplex(z)):
        s = np.abs(z)
        c = np.angle(z)
    else:
        s = np.abs(z)
        c = z.real
    ax.scatter(x, y, s=s, c=c, **kwds)
    xlabel = f"{xlabel} [{x_unit}]" if x_unit else xlabel
    ylabel = f"{ylabel} [{y_unit}]" if y_unit else ylabel
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xscale(xscale)
    ax.set_yscale(yscale)


def autoplot(x,
             y,
             z,
             xlabel='x',
             ylabel='y',
             zlabel='z',
             x_unit='',
             y_unit='',
             z_unit='',
             fig=None,
             ax=None,
             index=None,
             xscale='auto',
             yscale='auto',
             zscale='auto',
             max_lines=3,
             scatter_lim=1000,
             resolution=None,
             **kwds):
    """
    Plot a 2D array as a line plot or an image.

    Parameters:
        x (array): x values
        y (array): y values
        z (array): z values
        xlabel (str): x label
        ylabel (str): y label
        zlabel (str): z label
        x_unit (str): x unit
        y_unit (str): y unit
        z_unit (str): z unit
        fig (Figure): figure to plot on
        ax (Axes): axes to plot on
        index (int): index of the line to plot
        xscale (str): x scale 'auto', 'linear' or 'log'
        yscale (str): y scale 'auto', 'linear' or 'log'
        zscale (str): z scale 'auto', 'linear' or 'log'
        max_lines (int): maximum number of lines to plot
        **kwds: keyword arguments passed to plot_img or plot_lines
    """
    if ax is not None:
        fig = ax.figure
    if fig is None:
        fig = plt.gcf()
    if ax is None:
        ax = fig.add_subplot(111)

    x = np.asarray(x)
    y = np.asarray(y)
    z = np.asarray(z)

    if xscale == 'auto':
        if good_for_logscale(x):
            xscale = 'log'
        else:
            xscale = 'linear'
    if yscale == 'auto':
        if good_for_logscale(y):
            yscale = 'log'
        else:
            yscale = 'linear'
    if zscale == 'auto':
        if good_for_logscale(z):
            zscale = 'log'
        else:
            zscale = 'linear'

    if x.shape == y.shape == z.shape and z.size < scatter_lim:
        plot_scatter(x,
                     y,
                     z,
                     xlabel,
                     ylabel,
                     zlabel,
                     x_unit,
                     y_unit,
                     z_unit,
                     fig,
                     ax,
                     xscale=xscale,
                     yscale=yscale,
                     zscale=zscale,
                     **kwds)
    elif z.ndim == 2 and (len(y) <= max_lines or len(x) <= max_lines
                          or index is not None):
        plot_lines(x,
                   y,
                   z,
                   xlabel,
                   ylabel,
                   zlabel,
                   x_unit=x_unit,
                   y_unit=y_unit,
                   z_unit=z_unit,
                   xscale=xscale,
                   yscale=yscale,
                   zscale=zscale,
                   ax=ax,
                   index=index,
                   **kwds)
    else:
        plot_img(x,
                 y,
                 z,
                 xlabel,
                 ylabel,
                 zlabel,
                 x_unit=x_unit,
                 y_unit=y_unit,
                 z_unit=z_unit,
                 xscale=xscale,
                 yscale=yscale,
                 zscale=zscale,
                 fig=fig,
                 ax=ax,
                 resolution=resolution,
                 **kwds)
