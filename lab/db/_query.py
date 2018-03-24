import asyncio
import functools
import importlib
import sys
from abc import ABCMeta, abstractmethod
from collections import Awaitable, Iterable, OrderedDict

import ipywidgets as widgets
import numpy as np
from IPython.display import (HTML, Image, Markdown, clear_output, display,
                             set_matplotlib_formats)

from . import _schema
from .._plot import image_to_uri, make_image_in_process
from ._schema import Record


class QuerySetUI():
    def __init__(self, querySet):
        self.querySet = querySet
        self.widget = widgets.HTML()
        self.tableHTML = []
        self._tasks = []

    def display(self, start=0, stop=10, figsize=None):
        display(self.widget)

        self.tableHTML = ['' for i in range(stop-start)]

        def callback(future, pos):
            row = future.result()
            self.tableHTML[pos] = row
            self.update()

        for index, record in enumerate(self.querySet.query_set[start:stop]):
            #tableHTML[index+2] = self.tableRow(index+start, record, figsize)
            task = asyncio.ensure_future(self.tableRow(index+start, record, figsize))
            task.add_done_callback(functools.partial(callback, pos=index))
            self._tasks.append(task)
            #self.widget.value = ''.join(tableHTML)

    def update(self):
        style = '''<style>
        .tag-blue {background: #2d8cf0; color: #fff; border: 0;}
        .tag-red {background: #f02d2d; color: #fff; border: 0;}
        .tag-border {height: 24px; line-height: 24px; border: 1px solid #e9eaec!important;
            color: #495060!important; background: #fff!important; position: relative;}
        .tag {display: inline-block; height: 22px; line-height: 22px;
            margin: 2px 4px 2px 0; padding: 0 8px; border-radius: 3px;
            font-size: 12px; vertical-align: middle; opacity: 1;
            overflow: hidden; cursor: pointer;}
        .tag:hover {opacity: .85;}
        </style>'''

        table_head = '''<table class="output_html rendered_html"><thead>
        <tr><th>Index</th><th>Time</th><th>Title</th><th>User</th>
        <th>Tags</th><th>Parameters</th><th>Image</th></tr></thead><tbody>'''

        table_close = '''</tbody><caption>%d records in total.</caption>
        </table>''' % self.querySet.count()

        tableHTML = list((style, table_head, *self.tableHTML, table_close))

        self.widget.value = ''.join(tableHTML)

    async def tableRow(self, i, record, figsize):
        def tags_html(tags):
            html = ''
            for tag in tags:
                if tag[-1] == '!':
                    html += '<div class="tag tag-red">%s</div>' % tag
                else:
                    html += '<div class="tag tag-blue">%s</div>' % tag
            return html

        def params_html(params):
            html = ''
            for name, v in params.items():
                html += '<div class="tag tag-border">%s = %g %s</div>' % (name,
                                                                          v[0],
                                                                          v[1])
            return html

        return '''<tr><td>%(index)d</td>
            <td>%(time)s</td>
            <td>%(title)s</td>
            <td>%(user)s</td>
            <td>%(tags)s</td>
            <td>%(params)s</td>
            <td>%(image)s</td></tr>''' % {
            'index': i,
            'time': record.finished_time.strftime('%Y-%m-%d %H:%M:%S'),
            'title': record.title,
            'tags': tags_html(record.tags),
            'params': params_html(record.params),
            'user': record.user.fullname,
            'image': await self.plot(record, figsize)
        }

    async def plot(self, record, figsize):
        try:
            if record.app is None:
                return
            mod = importlib.import_module(record.app.module.fullname)
            app_cls = getattr(mod, record.app.name)
            img, width, height = await make_image_in_process(app_cls.plot, record.data, figsize=figsize)
            img_uri = image_to_uri(img, 'image/svg+xml')
        except Exception as e:
            print(e)
            img_uri = ''
        imgHTML = u'<img style="height: 30px" src="{}" alt="No Image"/>'.format(
            img_uri)
        return imgHTML


class QuerySet():
    def __init__(self, query_set):
        self.query_set = query_set
        self.ui = QuerySetUI(self)

    @functools.lru_cache(maxsize=32)
    def __getitem__(self, i):
        return self.query_set[i]

    def __iter__(self):
        self.__count = self.count()
        self.__index = 0
        return self

    def __next__(self):
        if self.__index < self.__count:
            return self.__getitem__(self.__index)
        else:
            raise StopIteration

    def count(self):
        return self.query_set.count()

    def display(self, start=0, stop=10, figsize=None):
        self.ui.display(start, stop, figsize)


def query(q=None, app=None, show_hidden=False, **kwds):
    if q is not None:
        qs = Record.objects(q).order_by('-finished_time')
    else:
        if app is not None:
            if isinstance(app, str):
                return query_by_app_name(app, show_hidden, version=kwds.pop('version', None))
            elif hasattr(app, '__DBDocument__'):
                kwds['app'] = app.__DBDocument__
            elif isinstance(app, _schema.Application):
                kwds['app'] = app
        if not show_hidden:
            kwds['hidden'] = False
        qs = Record.objects(**kwds).order_by('-finished_time')
    return QuerySet(qs)

def query_by_app_name(app_name, show_hidden=False, version=None):
    rec_q = {'app__in': []}
    app_q = {'name': app_name}
    if isinstance(version, int):
        app_q['version'] = version
    elif isinstance(version, str):
        if len(version.split('.')) == 3:
            app_q['version'] = int(version.split('.')[2])
        else:
            app_q['version_tag__istartswith'] = version
    for app in _schema.Application.objects(**app_q):
        rec_q['app__in'].append(app)
    if not show_hidden:
        rec_q['hidden'] = False
    qs = _schema.Record.objects(**rec_q).order_by('-finished_time')
    return QuerySet(qs)
