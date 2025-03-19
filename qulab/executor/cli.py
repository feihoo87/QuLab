import functools
import graphlib
import importlib
import os
import sys
from pathlib import Path

import click
from loguru import logger

from ..cli.config import get_config_value, log_options
from .load import (WorkflowType, find_unreferenced_workflows, get_entries,
                   load_workflow, make_graph)
from .schedule import CalibrationFailedError
from .schedule import maintain as maintain_workflow
from .schedule import run as run_workflow
from .transform import set_config_api
from .utils import workflow_template


@logger.catch(reraise=True)
def boot(script_path):
    """Run a script in a new terminal."""
    import subprocess
    import sys

    proc = subprocess.Popen([sys.executable, script_path])
    proc.communicate()


@logger.catch(reraise=True)
def check_toplogy(workflow: WorkflowType, code_path: str | Path) -> dict:
    graph = {}
    try:
        graphlib.TopologicalSorter(make_graph(workflow, graph,
                                              code_path)).static_order()
    except graphlib.CycleError as e:
        logger.error(
            f"Workflow {workflow.__workflow_id__} has a circular dependency: {e}"
        )
        raise e
    return graph


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
        @click.option(
            '--bootstrap',
            '-b',
            default=lambda: get_config_value("bootstrap", Path, command_name),
            help='The path of the bootstrap.')
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if 'code' in kwargs and kwargs['code'] is not None:
                code = os.path.expanduser(kwargs['code'])
                if code not in sys.path:
                    sys.path.insert(0, code)
            bootstrap = kwargs.pop('bootstrap')
            if bootstrap is not None:
                boot(bootstrap)
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
        f.write(workflow_template(workflow, list(deps)))
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
        set_config_api(api.query_config, api.update_config, api.export_config)
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
        set_config_api(api.query_config, api.update_config, api.export_config)
    click.echo(transform.query_config(key))


@click.command()
@click.argument('workflow')
@click.option('--plot', '-p', is_flag=True, help='Plot the report.')
@click.option('--no-dependents',
              '-n',
              is_flag=True,
              help='Do not run dependents.')
@click.option('--retry', '-r', default=1, type=int, help='Retry times.')
@click.option('--freeze', is_flag=True, help='Freeze the config table.')
@log_options
@command_option('run')
def run(workflow, code, data, api, plot, no_dependents, retry, freeze):
    """
    Run a workflow.

    If the workflow has entries, run all entries.
    If `--no-dependents` is set, only run the workflow itself.
    If `--retry` is set, retry the workflow when calibration failed.
    If `--freeze` is set, freeze the config table.
    If `--plot` is set, plot the report.
    If `--api` is set, use the api to get and update the config table.
    If `--code` is not set, use the current working directory.
    If `--data` is not set, use the `logs` directory in the code path.
    """
    logger.info(
        f'[CMD]: run {workflow} --code {code} --data {data} --api {api}'
        f'{" --plot" if plot else ""}'
        f'{" --no-dependents" if no_dependents else ""}'
        f' --retry {retry}'
        f'{" --freeze " if freeze else ""}')
    if api is not None:
        api = importlib.import_module(api)
        set_config_api(api.query_config, api.update_config, api.export_config)
    if code is None:
        code = Path.cwd()
    if data is None:
        data = Path(code) / 'logs'

    code = Path(os.path.expanduser(code))
    data = Path(os.path.expanduser(data))

    wf = load_workflow(workflow, code)
    check_toplogy(wf, code)

    for i in range(retry):
        try:
            if no_dependents:
                if hasattr(wf, 'entries'):
                    for entry in get_entries(wf, code):
                        run_workflow(entry,
                                     code,
                                     data,
                                     plot=plot,
                                     freeze=freeze)
                else:
                    run_workflow(wf, code, data, plot=plot, freeze=freeze)
            else:
                if hasattr(wf, 'entries'):
                    for entry in get_entries(wf, code):
                        maintain_workflow(entry,
                                          code,
                                          data,
                                          run=True,
                                          plot=plot,
                                          freeze=freeze)
                else:
                    maintain_workflow(wf,
                                      code,
                                      data,
                                      run=True,
                                      plot=plot,
                                      freeze=freeze)
            break
        except CalibrationFailedError as e:
            if i == retry - 1:
                raise e
            logger.warning(f'Calibration failed, retrying ({i + 1}/{retry})')
            continue


@click.command()
@click.argument('workflow')
@click.option('--retry', '-r', default=1, type=int, help='Retry times.')
@click.option('--plot', '-p', is_flag=True, help='Plot the report.')
@log_options
@command_option('maintain')
def maintain(workflow, code, data, api, retry, plot):
    """
    Maintain a workflow.

    If the workflow has entries, run all entries.
    If `--retry` is set, retry the workflow when calibration failed.
    If `--plot` is set, plot the report.
    If `--api` is set, use the api to get and update the config table.
    If `--code` is not set, use the current working directory.
    If `--data` is not set, use the `logs` directory in the code path.
    """
    logger.info(
        f'[CMD]: maintain {workflow} --code {code} --data {data} --api {api}'
        f' --retry {retry}'
        f'{" --plot" if plot else ""}')
    if api is not None:
        api = importlib.import_module(api)
        set_config_api(api.query_config, api.update_config, api.export_config)
    if code is None:
        code = Path.cwd()
    if data is None:
        data = Path(code) / 'logs'

    code = Path(os.path.expanduser(code))
    data = Path(os.path.expanduser(data))

    wf = load_workflow(workflow, code)
    check_toplogy(wf, code)

    for i in range(retry):
        try:
            if hasattr(wf, 'entries'):
                for entry in get_entries(wf, code):
                    maintain_workflow(entry,
                                      code,
                                      data,
                                      run=False,
                                      plot=plot,
                                      freeze=False)
            else:
                maintain_workflow(wf,
                                  code,
                                  data,
                                  run=False,
                                  plot=plot,
                                  freeze=False)
            break
        except CalibrationFailedError as e:
            if i == retry - 1:
                raise e
            logger.warning(f'Calibration failed, retrying ({i + 1}/{retry})')
            continue
