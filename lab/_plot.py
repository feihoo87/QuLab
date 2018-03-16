import base64
import io

import ipywidgets as widgets
import matplotlib.pyplot as plt
from IPython.display import (HTML, Image, Markdown, clear_output, display,
                             set_matplotlib_formats)


class NotebookFigure():
    def __init__(self, num=None, figsize=None, dpi=None, facecolor=None, edgecolor=None, frameon=True, clear=True):
        self.out = widgets.Output()
        self.out.layout.height = '300px'
        self.kwds = dict(num=num, figsize=figsize, dpi=dpi, facecolor=facecolor,
                         edgecolor=edgecolor, frameon=frameon, clear=clear)
        self.displayed = False

    def display(self):
        display(self.out)
        self.displayed = True


__figs = {}


def make_image(func, data, fig_format='svg', **kwds):
    content_type = {
        'png': 'image/png',
        'svg': 'image/svg+xml'
    }[fig_format]

    fig = __figs.get(tuple(kwds.items()), None)
    if fig is None:
        fig = plt.figure(**kwds)
        __figs[tuple(kwds.items())] = fig
    else:
        fig.clear()
    func(fig, data)
    buff = io.BytesIO()
    fig.savefig(buff, format=fig_format)
    img = 'data:{0};base64,{1}'.format(
        content_type,
        base64.b64encode(buff.getvalue()).decode('utf-8'))
    return img, int(fig.get_dpi()*fig.get_figheight())


__app_figs = {}


def draw(method, data, app):
    if hasattr(app, '_figure') and app._figure is not None:
        figure = app._figure
    elif app.__class__.__name__ in __app_figs.keys():
        figure = __app_figs[app.__class__.__name__]
    else:
        return
    img, height = make_image(method, data, fig_format='svg', **figure.kwds)
    with figure.out:
        figure.out.layout.height = '%dpx' % (height+12)
        clear_output()
        display(
            HTML(u'<img style="height: %dpx" src="%s" alt="Red dot"/>' % (height, img)))


def make_figure_for_app(app, *args, **kwds):
    app._figure = NotebookFigure(*args, **kwds)
    app._figure.display()


def make_figures_for_App(app_name, *args, **kwds):
    fig = NotebookFigure(*args, **kwds)
    __app_figs[app_name] = fig
    fig.display()
