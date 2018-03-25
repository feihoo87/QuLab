import getpass

import ipywidgets as widgets
from IPython.display import (HTML, Image, Markdown, clear_output, display,
                             set_matplotlib_formats)


def get_login_info():
    username = input('User Name > ')
    password = getpass.getpass(prompt='Password > ')
    return username, password


class ApplicationUI:
    def __init__(self, app):
        self.app = app
        self._ProgressWidget = widgets.FloatProgress(
            0, description=self.app.__class__.__name__)

    def setProcess(self, value):
        self._ProgressWidget.value = value

    def display(self):
        display(self._ProgressWidget)


def display_source_code(source_code, language='python'):
    display(Markdown("```%s\n%s\n```" % (language, source_code)))


def listApps(apps):
    table = [
        ' name | version | author | discription | time ',
        '----|----|----|----|----',
    ]
    for app in apps:
        discription = app.discription.split('\n')[0] if app.discription is not None else ''
        table.append('%s|v%s|%s|%s|%s' % (app.name, app.version.text,
                                         app.author.fullname, discription,
                                         app.created_time.strftime('%Y-%m-%d %H:%M:%S')))
    display(Markdown('\n'.join(table)))


def list_drivers(drivers):
    table = [
        ' name | version | modules | time ',
        '----|----|----|----',
    ]
    for driver in drivers:
        module = driver.module
        if module is None:
            table.append('%s|%s| Error! Module for driver not set |N/A' % (
                driver.name, driver.version))
            continue
        table.append('%s|%s|%s|%s' % (driver.name, driver.version,
            module.fullname, module.created_time.strftime('%Y-%m-%d %H:%M:%S')))
        if not module.is_package:
            continue
        for sub_module in module.modules:
            table.append('%s|%s|%s|%s' % ('', '', sub_module.fullname,
                sub_module.created_time.strftime('%Y-%m-%d %H:%M:%S')))
    display(Markdown('\n'.join(table)))


def list_instruments(instruments):
    table = [
        '| name | host | address | driver |',
        '|:----|:----|:----|:----|',
    ]
    for inst in instruments:
        table.append('|%s|%s|%s|%s|' %
                     (inst.name, inst.host, inst.address,
                      inst.driver.name if inst.driver is not None else 'None'))
    display(Markdown('\n'.join(table)))
