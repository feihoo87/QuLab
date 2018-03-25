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
    th = ['package', 'name', 'version', 'author', 'discription', 'time']
    table = [
        '<table><thead><tr>',
        *['<th style="text-align:left">%s</th>' % item for item in th],
        '</tr></thead><tbody>'
    ]
    for app in apps:
        discription = app.discription.split('\n')[0] if app.discription is not None else ''
        tr = ['<td style="text-align:left">%s</td>' % item for item in (
            app.package, app.name, app.version.text, app.author.fullname,
            discription, app.created_time.strftime('%Y-%m-%d %H:%M:%S'))]
        table.append(''.join(['<tr>', *tr, '</tr>']))

    table.append('</tbody></table>')
    display(HTML(''.join(table)))


def list_drivers(drivers):
    th = ['name', 'version', 'modules', 'time']
    table = [
        '<table><thead><tr>',
        *['<th style="text-align:left">%s</th>' % item for item in th],
        '</tr></thead><tbody>'
    ]
    for driver in drivers:
        module = driver.module
        if module is None:
            tr = ['<td style="text-align:left">%s</td>' % item for item in (
                driver.name, driver.version, 'Error! Module for driver not set', 'N/A')]
            table.append(''.join(['<tr>', *tr, '</tr>']))
            continue
        tr = ['<td style="text-align:left">%s</td>' % item for item in (
            driver.name, driver.version, module.fullname,
            module.created_time.strftime('%Y-%m-%d %H:%M:%S'))]
        table.append(''.join(['<tr>', *tr, '</tr>']))
        if not module.is_package:
            continue
        for sub_module in module.modules:
            tr = ['<td style="text-align:left">%s</td>' % item for item in (
                '', '', module.fullname,
                module.created_time.strftime('%Y-%m-%d %H:%M:%S'))]
            table.append(''.join(['<tr>', *tr, '</tr>']))

    table.append('</tbody></table>')
    display(HTML(''.join(table)))


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
