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
        table.append('%s|%s.%d|%s|%s|%s' % (app.name, app.version_tag, app.version,
                                         app.author.fullname, app.discription, app.created_time.strftime('%Y-%m-%d %H:%M:%S')))
    display(Markdown('\n'.join(table)))


def list_drivers(drivers):
    table = [
        ' name | files | time ',
        '----|:----|----',
    ]
    for driver in drivers:
        table.append('%s|%s|%s' % (driver.name, '', ''))
        for f in driver.files:
            table.append('%s|%s|%s' % ('', f.name, f.modified_time))
    display(Markdown('\n'.join(table)))


def list_instruments(instruments):
    table = [
        '| name | host | address | driver |',
        '|:----|:----|:----|:----|',
    ]
    for inst in instruments:
        table.append('|%s|%s|%s|%s|' %
                     (inst.name, inst.host, inst.address, inst.driver.name))
    display(Markdown('\n'.join(table)))
