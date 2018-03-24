import asyncio
import base64
import functools
import io

import ipywidgets as widgets
import matplotlib as mpl
import matplotlib.pyplot as plt
from IPython.display import (HTML, Image, Markdown, clear_output, display,
                             set_matplotlib_formats)
from matplotlib.backends import backend_svg


class NotebookFigure():
    def __init__(self, figsize=None, dpi=None, facecolor=None, edgecolor=None, frameon=True):
        self.image = widgets.Image(format = 'svg+xml')
        self.kwds = dict(figsize=figsize, dpi=dpi, facecolor=facecolor,
                         edgecolor=edgecolor, frameon=frameon)

    def display(self):
        display(self.image)


__figs = {}

def make_image(func, data, fig_format='svg', **kwds):
    content_type = {
        'png': 'image/png',
        'svg': 'image/svg+xml'
    }[fig_format]

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
    height = int(fig.get_dpi()*fig.get_figheight())
    width = int(fig.get_dpi()*fig.get_figwidth())
    return img, width, height


def image_to_uri(img, content_type):
    uri = 'data:{0};base64,{1}'.format(
        content_type,
        base64.b64encode(img).decode('utf-8'))
    return uri


async def make_image_in_process(func, data, **kwds):
    from ._bootstrap import p_executor
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(p_executor,
        functools.partial(make_image, func, data, **kwds))


__app_figs = {}


def draw(method, data, app):
    if hasattr(app, '_figure') and app._figure is not None:
        figure = app._figure
    elif app.__class__.__name__ in __app_figs.keys():
        for fig in __app_figs[app.__class__.__name__]:
            if not hasattr(fig, '_app') or fig._app == app or fig._app.is_done():
                fig._app = app
                figure = fig
                break
        else:
            return
    else:
        return

    def callback(future, figure):
        img, width, height = future.result()
        figure.image.width = width
        figure.image.height = height
        figure.image.value = img

    task = asyncio.ensure_future(make_image_in_process(method, data, **figure.kwds))
    task.add_done_callback(functools.partial(callback, figure=figure))


def make_figure_for_app(app, *args, **kwds):
    app._figure = NotebookFigure(*args, **kwds)
    app._figure.display()


def make_figures_for_App(app_name, num=1, *args, **kwds):
    __app_figs[app_name] = [NotebookFigure(*args, **kwds) for i in range(num)]
    widget = widgets.HBox([fig.image for fig in __app_figs[app_name]])
    display(widget)
