import functools
import math
from pathlib import Path

import dill
import ipywidgets as widgets
import zmq
from IPython.display import display
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from qulab.sys.rpc.zmq_socket import ZMQContextManager

from .record import Record
from .scan import default_server
from .server import get_local_record


def get_record(id,
               database=default_server,
               socket=None,
               session=None) -> Record:
    if isinstance(database, str) and database.startswith('tcp://'):
        with ZMQContextManager(zmq.DEALER, connect=database,
                               socket=socket) as socket:
            socket.send_pyobj({
                'method': 'record_description',
                'record_id': id
            })
            d = dill.loads(socket.recv_pyobj())
            if d is None:
                raise ValueError(f'No record with id {id}')
            d.id = id
            d.database = database
            d._file = None
            d._sock = socket
            return d
    else:
        if session is None:
            db_file = Path(database) / 'data.db'
            engine = create_engine(f'sqlite:///{db_file}')
            Session = sessionmaker(bind=engine)
            with Session() as session:
                return get_local_record(session, id, database)
        else:
            return get_local_record(session, id, database)


def load_record(file):
    return Record.load(file)


def _format_tag(tag):
    if tag.startswith('!'):
        return f'<code style="color: white; background: red">{tag}</code>'
    elif tag.startswith('?'):
        return f'<code style="background: orange">{tag}</code>'
    elif tag.startswith('@'):
        return f'<code style="color: white; background: green">{tag}</code>'
    elif tag.startswith('#'):
        return f'<code style="color: white; background: blue">{tag}</code>'
    elif tag.startswith('$'):
        return f'<code style="color: white; background: purple">{tag}</code>'
    elif tag.startswith('%'):
        return f'<code style="color: white; background: brown">{tag}</code>'
    else:
        return f'<code>{tag}</code>'


def _format_value(title, value):
    if title in ['ID', 'App']:
        return str(value)
    elif title in ['created time']:
        return str(value).split('.')[0]
    elif title in ['tags']:
        tags = sorted(value)
        if len(tags) <= 6:
            tags = [_format_tag(t) for t in tags]
        elif len(tags) <= 12:
            tags = [_format_tag(t) for t in tags[:6]
                    ] + ['<br />'] + [_format_tag(t) for t in tags[6:]]
        elif len(tags) <= 18:
            tags = [_format_tag(t) for t in tags[:6]] + ['<br />'] + [
                _format_tag(t) for t in tags[6:12]
            ] + ['<br />'] + [_format_tag(t) for t in tags[12:]]
        else:
            tags = [_format_tag(t) for t in tags[:6]] + ['<br />'] + [
                _format_tag(t) for t in tags[6:12]
            ] + ['<br />'] + [_format_tag(t) for t in tags[12:17]] + ['...']
        return ' '.join(tags)
    else:
        return repr(value)


def _format_table(table):
    tb = [
        """<div class="output_subarea output_markdown rendered_html" dir="auto">"""
        """<table>"""
        """<thead>"""
        """<tr>"""
    ]
    for s in table['header']:
        tb.append(f'<th style="text-align: center">{s}</th>')
    tb.append("""</tr></thead><tbody>""")

    for row in table["body"]:
        r = ["<tr>"]
        for k, v in zip(table['header'], row):
            s = _format_value(k, v)
            r.append(f'<td style="text-align: center">{s}</td>')
        r.append("</tr>")
        tb.append(''.join(r))
    tb.append("""</tbody></table>"""
              """</div>""")
    return ''.join(tb)


class _QueryState():

    def __init__(self):
        self.table = None
        self.apps = {}
        self.page = 1
        self.total = 0
        self.app_prefix = []
        self.app_name = '*'
        self.records_per_page = 10

    def list_apps(self, prefix=None):
        common = ('..', '*') if prefix else ('*', )

        if prefix is None:
            prefix = self.app_prefix
        d = self.apps
        for p in prefix:
            try:
                d = d[p]
            except:
                return common
        if isinstance(d, dict):
            return common + tuple(sorted(d.keys()))
        elif prefix:
            return prefix[-1]
        else:
            return common + tuple(sorted(self.apps.keys()))


__query_state = _QueryState()


def _update_state(app_prefix,
                  app_name,
                  tags,
                  offset,
                  after,
                  before,
                  records_per_page,
                  database='tcp://127.0.0.1:6789'):

    state = __query_state

    app_pattern = '.'.join(app_prefix + [app_name])
    if app_pattern == '*':
        app_pattern = None

    if app_name == '..':
        app_prefix = app_prefix[:-1]
        app_name = '*'
    elif app_name == '*':
        pass
    else:
        app_prefix = app_prefix + [app_name]
        app_name = '*'

    if isinstance(database, str) and database.startswith('tcp://'):
        with ZMQContextManager(zmq.DEALER, connect=database) as socket:
            socket.send_pyobj({
                'method': 'record_query',
                'app': app_pattern,
                'tags': tags,
                'offset': offset,
                'limit': records_per_page,
                'before': before,
                'after': after
            })
            total, apps, table = socket.recv_pyobj()
    else:
        from .curd import query_record
        from .models import create_engine, sessionmaker

        url = f'sqlite:///{database}/data.db'

        engine = create_engine(url)
        Session = sessionmaker(bind=engine)
        with Session() as db:
            total, apps, table = query_record(db,
                                              offset=offset,
                                              limit=records_per_page,
                                              app=app_pattern,
                                              tags=tags,
                                              before=before,
                                              after=after)
    state.table = table
    state.apps = apps
    state.total = total
    state.records_per_page = records_per_page
    app_list = state.list_apps(app_prefix)
    if isinstance(app_list, str):
        state.app_name = app_prefix[-1]
    else:
        state.app_prefix = app_prefix
        state.app_name = '*'
    return total


def _update_view(ui_widgets):
    state = __query_state

    page = state.page
    total = state.total
    records_per_page = state.records_per_page

    app_options = state.list_apps(state.app_prefix)
    ui_widgets['app_prefix'].value = 'App:' + '.'.join(state.app_prefix)
    handlers = ui_widgets['app']._trait_notifiers['value']['change']
    ui_widgets['app']._trait_notifiers['value']['change'] = handlers[:1]
    ui_widgets['app'].options = app_options
    ui_widgets['app']._trait_notifiers['value']['change'] = handlers
    ui_widgets['app'].value = state.app_name

    offset = (page - 1) * records_per_page
    if offset < records_per_page:
        ui_widgets['bt_pre'].disabled = True
    else:
        ui_widgets['bt_pre'].disabled = False

    ui_widgets['table'].value = _format_table(state.table)
    if total - offset <= records_per_page:
        ui_widgets['bt_next'].disabled = True
    else:
        ui_widgets['bt_next'].disabled = False
    ui_widgets[
        'page_num_label'].value = f"{page} | {math.ceil(total/10)} pages"


def _get_query_params(state: _QueryState, ui_widgets: dict):
    page = state.page
    records_per_page = state.records_per_page
    tags = [t.strip() for t in ui_widgets['tags'].value.split(',') if t]
    offset = (page - 1) * records_per_page
    after = ui_widgets['after'].value
    before = ui_widgets['before'].value

    if state.app_name == '..' and len(state.app_prefix) == 1:
        state.app_prefix = []
        state.app_name = '*'

    return state.app_prefix, state.app_name, tags, offset, after, before, records_per_page


def _on_pre_bt_clicked(bt, ui_widgets):
    __query_state.page -= 1
    _update_state(*_get_query_params(__query_state, ui_widgets))
    _update_view(ui_widgets)


def _on_next_bt_clicked(bt, ui_widgets):
    __query_state.page += 1
    _update_state(*_get_query_params(__query_state, ui_widgets))
    _update_view(ui_widgets)


def _on_app_changed(changes, ui_widgets, stack=[]):
    if changes['name'] not in ['value', 'index']:
        stack.append(changes['name'])
        return
    if stack and changes['name'] == 'index':
        stack.clear()
        return

    __query_state.app_name = ui_widgets['app'].value
    __query_state.page = 1
    _update_state(*_get_query_params(__query_state, ui_widgets))
    _update_view(ui_widgets)


def _on_after_changed(changes, ui_widgets):
    if changes['name'] != 'value':
        return
    __query_state.page = 1
    _update_state(*_get_query_params(__query_state, ui_widgets))
    _update_view(ui_widgets)


def _on_before_changed(changes, ui_widgets):
    if changes['name'] != 'value':
        return
    __query_state.page = 1
    _update_state(*_get_query_params(__query_state, ui_widgets))
    _update_view(ui_widgets)


def _on_tags_submit(tags, ui_widgets):
    __query_state.page = 1
    _update_state(*_get_query_params(__query_state, ui_widgets))
    _update_view(ui_widgets)


def lookup(app=None, limit=10, database=default_server):
    after = widgets.DatePicker()
    before = widgets.DatePicker()
    app_prefix = widgets.Label('App:')
    app_name = widgets.Dropdown(
        options=[
            '*',
        ],
        value='*',
        disabled=False,
    )
    bt_pre = widgets.Button(description='<<')
    bt_next = widgets.Button(description='>>')
    tags = widgets.Text()
    page_num_label = widgets.Label('1 | * pages')
    row1 = widgets.HBox(
        [bt_pre, page_num_label, bt_next, app_prefix, app_name])
    row2 = widgets.HBox([widgets.Label('Between:'), after, before])
    row3 = widgets.HBox([widgets.Label('  Tags :'), tags])
    table = widgets.HTML()
    box = widgets.VBox([row1, row2, row3, table])

    ui_widgets = {
        'app_prefix': app_prefix,
        'app': app_name,
        'before': before,
        'after': after,
        'tags': tags,
        'table': table,
        'page_num_label': page_num_label,
        'bt_pre': bt_pre,
        'bt_next': bt_next,
    }

    __query_state.records_per_page = limit
    if app is not None:
        __query_state.app_prefix = app.split('.')
        __query_state.app_name = '*'

    _update_state(*_get_query_params(__query_state, ui_widgets),
                  database=database)
    _update_view(ui_widgets)

    bt_pre.on_click(
        functools.partial(_on_pre_bt_clicked, ui_widgets=ui_widgets))
    bt_next.on_click(
        functools.partial(_on_next_bt_clicked, ui_widgets=ui_widgets))
    after.observe(functools.partial(_on_after_changed, ui_widgets=ui_widgets),
                  names='value')
    before.observe(functools.partial(_on_before_changed,
                                     ui_widgets=ui_widgets),
                   names='value')
    app_name.observe(functools.partial(_on_app_changed, ui_widgets=ui_widgets),
                     names='value')
    tags.on_submit(functools.partial(_on_tags_submit, ui_widgets=ui_widgets))

    display(box)


def lookup_list(*, full=False):
    if __query_state.table is None:
        return []
    if full:
        return __query_state.table['body']
    else:
        return [r[0] for r in __query_state.table['body']]
