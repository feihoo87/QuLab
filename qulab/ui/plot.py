import asyncio
import base64
import functools
import io

import ipywidgets as widgets
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from IPython.display import (HTML, Image, Markdown, clear_output, display,
                             set_matplotlib_formats)
from matplotlib.backends import backend_svg


def image_to_uri(img, content_type):
    uri = 'data:{0};base64,{1}'.format(content_type,
                                       base64.b64encode(img).decode('utf-8'))
    return uri


class NotebookFigure():
    def __init__(self,
                 fig_format='png',
                 figsize=None,
                 dpi=None,
                 facecolor=None,
                 edgecolor=None,
                 frameon=True):
        #self.image = widgets.Image(format='svg+xml')
        self.image = widgets.Image(format=fig_format)
        self.kwds = dict(figsize=figsize,
                         dpi=dpi,
                         facecolor=facecolor,
                         edgecolor=edgecolor,
                         frameon=frameon,
                         fig_format=fig_format)

    def display(self):
        display(self.image)


__figs = {}


def make_image(func, data, fig_format='png', **kwds):
    content_type = {'png': 'image/png', 'svg': 'image/svg+xml'}[fig_format]

    fig = __figs.get(tuple(kwds.items()), None)
    if fig is None:
        fig = mpl.figure.Figure(**kwds)
        canvas = backend_svg.FigureCanvasSVG(fig)
        __figs[tuple(kwds.items())] = fig
    else:
        fig.clear()
    func(fig, data)
    buff = io.BytesIO()
    fig.savefig(buff, format=fig_format)
    img = buff.getvalue()
    height = int(fig.get_dpi() * fig.get_figheight())
    width = int(fig.get_dpi() * fig.get_figwidth())
    return img, width, height


async def make_image_in_process(func, data, **kwds):
    return make_image(func, data, **kwds)


def draw(figure, method, data, last_task=None):
    def callback(future, figure):
        img, width, height = future.result()
        figure.image.width = width
        figure.image.height = height
        figure.image.value = img
        
    if last_task is not None:
        if not last_task.done():
            return

    task = asyncio.ensure_future(
        make_image_in_process(method, data, **figure.kwds))
    task.add_done_callback(functools.partial(callback, figure=figure))
    
    return task


def figure(*args, **kwds):
    figure = NotebookFigure(*args, **kwds)
    return figure


def show(plot, get_data, fig=None):
    if fig is None:
        fig = figure()

    qbt = widgets.Button(description='Quit')
    qbt.value = False

    def cb(bt):
        qbt.value = True
        qbt.disabled = True

    qbt.on_click(cb)

    async def run():
        task = None
        for data in get_data():
            task = draw(fig, plot, data, task)
            if qbt.value == True:
                break
            await asyncio.sleep(0.05)

    fig.display()
    display(qbt)
    asyncio.ensure_future(run())
    