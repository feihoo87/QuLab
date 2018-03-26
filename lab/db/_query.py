import functools

from . import _schema


def query_records_by_app_name(app_name, show_hidden=False, version=None):
    rec_q = {'app__in': []}
    for app in _schema.getApplication(name=app_name, version=version, many=True):
        rec_q['app__in'].append(app)
    if not show_hidden:
        rec_q['hidden'] = False
    return _schema.Record.objects(**rec_q).order_by('-finished_time')


def query_records(q=None, app=None, show_hidden=False, **kwds):
    if q is not None:
        return _schema.Record.objects(q).order_by('-finished_time')
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
        return _schema.Record.objects(**kwds).order_by('-finished_time')
