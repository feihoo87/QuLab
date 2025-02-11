import functools
import importlib
import os
import sys
from pathlib import Path

import click
from loguru import logger

from ..cli.config import ENV_PREFIX, get_config_value, log_options
from .load import find_unreferenced_workflows, get_entries, load_workflow
from .schedule import maintain as maintain_workflow
from .schedule import run as run_workflow
from .transform import set_config_api
from .utils import workflow_template


def command_option(command_name):
    """命令专属配置装饰器工厂"""

    def decorator(func):

        @click.option(
            '--code',
            '-c',
            default=lambda: get_config_value("code", str, command_name),
            help='The path of the code.')
        @click.option(
            '--data',
            '-d',
            default=lambda: get_config_value("data", str, command_name),
            help='The path of the data.')
        @click.option(
            '--api',
            '-a',
            default=lambda: get_config_value("api", str, command_name),
            help='The modlule name of the api.')
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


@click.command()
@click.argument('workflow')
@click.option('--code',
              '-c',
              default=lambda: get_config_value("code", str, 'create'),
              help='The path of the code.')
def create(workflow, code):
    """
    Create a new workflow file.
    """
    logger.info(f'[CMD]: create {workflow} --code {code}')
    if code is None:
        code = Path.cwd()

    fname = Path(code) / f'{workflow}'
    fname = Path(os.path.expanduser(fname))
    if fname.exists():
        click.echo(f'{workflow} already exists')
        return

    fname.parent.mkdir(parents=True, exist_ok=True)
    deps = find_unreferenced_workflows(code)

    with open(fname, 'w') as f:
        f.write(workflow_template(list(deps)))
    click.echo(f'{workflow} created')


@click.command()
@click.argument('key')
@click.argument('value', type=str)
@click.option('--api',
              '-a',
              default=lambda: get_config_value("api", str, 'set'),
              help='The modlule name of the api.')
def set(key, value, api):
    """
    Set a config.
    """
    logger.info(f'[CMD]: set {key} {value} --api {api}')
    from . import transform
    if api is not None:
        api = importlib.import_module(api)
        set_config_api(api.query_config, api.update_config)
    try:
        value = eval(value)
    except:
        pass
    transform.update_config({key: value})


@click.command()
@click.argument('key')
@click.option('--api',
              '-a',
              default=lambda: get_config_value("api", str, 'get'),
              help='The modlule name of the api.')
def get(key, api):
    """
    Get a config.
    """
    logger.info(f'[CMD]: get {key} --api {api}')
    from . import transform
    if api is not None:
        api = importlib.import_module(api)
        set_config_api(api.query_config, api.update_config)
    click.echo(transform.query_config(key))


@click.command()
@click.argument('workflow')
@click.option('--plot', '-p', is_flag=True, help='Plot the result.')
@click.option('--no-dependents',
              '-n',
              is_flag=True,
              help='Do not run dependents.')
@log_options
@command_option('run')
def run(workflow, code, data, api, plot, no_dependents):
    """
    Run a workflow.
    """
    logger.info(
        f'[CMD]: run {workflow} --code {code} --data {data} --api {api} --plot {plot} --no-dependents {no_dependents}'
    )
    if api is not None:
        api = importlib.import_module(api)
        set_config_api(api.query_config, api.update_config)
    if code is None:
        code = Path.cwd()
    if data is None:
        data = Path(code) / 'logs'

    code = Path(os.path.expanduser(code))
    data = Path(os.path.expanduser(data))

    wf = load_workflow(workflow, code)

    if no_dependents:
        if hasattr(wf, 'entries'):
            for entry in get_entries(wf, code):
                run_workflow(entry, code, data, plot=plot)
        else:
            run_workflow(wf, code, data, plot=plot)
    else:
        if hasattr(wf, 'entries'):
            for entry in get_entries(wf, code):
                maintain_workflow(entry, code, data, run=True, plot=plot)
        else:
            maintain_workflow(wf, code, data, run=True, plot=plot)


@click.command()
@click.argument('workflow')
@click.option('--plot', '-p', is_flag=True, help='Plot the result.')
@log_options
@command_option('maintain')
def maintain(workflow, code, data, api, plot):
    """
    Maintain a workflow.
    """
    logger.info(
        f'[CMD]: maintain {workflow} --code {code} --data {data} --api {api} --plot {plot}'
    )
    if api is not None:
        api = importlib.import_module(api)
        set_config_api(api.query_config, api.update_config)
    if code is None:
        code = Path.cwd()
    if data is None:
        data = Path(code) / 'logs'

    code = Path(os.path.expanduser(code))
    data = Path(os.path.expanduser(data))

    wf = load_workflow(workflow, code)
    if hasattr(wf, 'entries'):
        for entry in get_entries(wf, code):
            maintain_workflow(entry, code, data, run=False, plot=plot)
    else:
        maintain_workflow(wf, code, data, run=False, plot=plot)
