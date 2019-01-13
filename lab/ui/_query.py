import asyncio
import functools
import importlib

import ipywidgets as widgets
from IPython.display import display

from .._plot import image_to_uri, make_image_in_process


class QuerySetUI():
    def __init__(self, querySet):
        self.querySet = querySet
        self.widget = widgets.HTML()
        self.tableHTML = []
        self._tasks = []

    cols_formater = {
        'Index': ['<th>Index</th>',
            lambda i,r: '<td>%d</td>' % i],
        'Id': ['<th>ID</th>',
            lambda i,r: '<td>%s</td>' % r.id],
        'Time': ['<th style="text-align:left">Time</th>',
            lambda i,r: '<td style="text-align:left">%s</td>' % r.finished_time.strftime('%Y-%m-%d %H:%M:%S')],
        'Title': ['<th style="text-align:left">Title</th>',
            lambda i,r: '<td style="text-align:left">%s</td>' % r.title],
        'User': ['<th style="text-align:left">User</th>',
            lambda i,r: '<td style="text-align:left">%s</td>' % r.user.fullname],
        'Tags': ['<th>Tags</th>',
            lambda i,r: '<td>%s</td>' % ''.join(['<div class="tag %s">%s</div>' % ('tag-red' if tag[-1]=='!' else 'tag-blue', tag) for tag in r.tags])],
        'Settings': ['<th>Settings</th>',
            lambda i,r: '<td>%s</td>' % ''.join(['<div class="tag tag-border">%s = %r</div>' % (k, v) for k,v in r.settings.items()])],
        'Parameters': ['<th>Parameters</th>',
            lambda i,r: '<td>%s</td>' % ''.join(['<div class="tag tag-border">%s = %g %s</div>' % (k, v[0], v[1]) for k,v in r.params.items()])],
        'Image': ['<th>Image</th>', None]
    }

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

    def display(self, start=0, stop=10,
        cols=['Index', 'Time', 'Title', 'User', 'Tags', 'Parameters', 'Image'],
        figsize=None):

        display(self.widget)

        table_begin = '''<table class="output_html rendered_html"><thead>
        <tr>%s</tr></thead><tbody>''' % self.tableHead(cols)

        table_end = '''</tbody><caption>%d records in total.</caption>
        </table>''' % self.querySet.count()

        self.tableHTML = ['' for i in range(stop-start)]
        self.update(table_begin, table_end)

        def callback(future, pos):
            row = future.result()
            self.tableHTML[pos] = row
            self.update(table_begin, table_end)

        loop = asyncio.get_event_loop()
        _new_loop = False
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _new_loop = True

        for index, record in enumerate(self.querySet.query_set[start:stop]):
            #tableHTML[index+2] = self.tableRow(index+start, record, figsize)
            task = asyncio.ensure_future(self.tableRow(cols, index+start, record, figsize))
            task.add_done_callback(functools.partial(callback, pos=index))
            self._tasks.append(task)
            #self.widget.value = ''.join(tableHTML)

        if not loop.is_running():
            loop.run_until_complete(asyncio.gather(*self._tasks))
        if _new_loop:
            loop.close()

    def update(self, table_begin, table_end):
        tableHTML = list((self.style, table_begin, *self.tableHTML, table_end))
        self.widget.value = ''.join(tableHTML)

    def tableHead(self, cols):
        return ''.join([self.cols_formater[col][0] for col in cols])

    async def tableRow(self, cols, i, record, figsize):
        return '''<tr>%s</tr>''' % ''.join([
            self.cols_formater[col][1](i, record) if col != 'Image'
            else '<td>%s</td>' % await self.plot(record, figsize)
            for col in cols])

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
