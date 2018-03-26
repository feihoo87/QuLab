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

    def display(self, start=0, stop=10, figsize=None):
        display(self.widget)

        self.tableHTML = ['' for i in range(stop-start)]
        self.update()

        def callback(future, pos):
            row = future.result()
            self.tableHTML[pos] = row
            self.update()

        loop = asyncio.get_event_loop()
        _new_loop = False
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _new_loop = True

        for index, record in enumerate(self.querySet.query_set[start:stop]):
            #tableHTML[index+2] = self.tableRow(index+start, record, figsize)
            task = asyncio.ensure_future(self.tableRow(index+start, record, figsize))
            task.add_done_callback(functools.partial(callback, pos=index))
            self._tasks.append(task)
            #self.widget.value = ''.join(tableHTML)

        if not loop.is_running():
            loop.run_until_complete(asyncio.gather(*self._tasks))
        if _new_loop:
            loop.close()

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
        <tr><th>Index</th><th style="text-align:left">Time</th>
        <th style="text-align:left">Title</th><th style="text-align:left">User</th>
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
            <td style="text-align:left">%(time)s</td>
            <td style="text-align:left">%(title)s</td>
            <td style="text-align:left">%(user)s</td>
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
