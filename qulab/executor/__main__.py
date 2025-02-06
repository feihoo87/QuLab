import functools
import importlib
import sys, os
from pathlib import Path

import click
from loguru import logger

from .load import find_unreferenced_workflows
from .schedule import maintain as maintain_workflow
from .schedule import run as run_workflow
from .transform import set_config_api
from .utils import workflow_template


def log_options(func):

    @click.option("--debug", is_flag=True, help="Enable debug mode.")
    @click.option("--log", type=str, help="Log file path.")
    @functools.wraps(func)  # 保持函数元信息
    def wrapper(*args, log=None, debug=False, **kwargs):
        print(f"{func} {log=}, {debug=}")
        if log is None and not debug:
            logger.remove()
            logger.add(sys.stderr, level='INFO')
        elif log is None and debug:
            logger.remove()
            logger.add(sys.stderr, level='DEBUG')
        elif log is not None and not debug:
            logger.configure(handlers=[dict(sink=log, level='INFO')])
        elif log is not None and debug:
            logger.configure(handlers=[
                dict(sink=log, level='DEBUG'),
                dict(sink=sys.stderr, level='DEBUG')
            ])
        return func(*args, **kwargs)

    return wrapper


@click.group()
def cli():
    pass


@click.command()
@click.argument('workflow')
@click.option('--code', '-c', default=None, help='The path of the code.')
def create(workflow, code):
    """
    Create a new workflow file.
    """
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
@click.argument('workflow')
@click.option('--code', '-c', default=None, help='The path of the code.')
@click.option('--data', '-d', default=None, help='The path of the data.')
@click.option('--api', '-a', default=None, help='The modlule name of the api.')
@click.option('--plot', '-p', is_flag=True, help='Plot the result.')
@click.option('--no-dependents',
              '-n',
              is_flag=True,
              help='Do not run dependents.')
@log_options
def run(workflow, code, data, api, plot, no_dependents):
    """
    Run a workflow.
    """
    if api is not None:
        api = importlib.import_module(api)
        set_config_api(api.query_config, api.update_config)
    if code is None:
        code = Path.cwd()
    if data is None:
        data = Path(code) / 'logs'

    code = Path(os.path.expanduser(code))
    data = Path(os.path.expanduser(data))

    if no_dependents:
        run_workflow(workflow, code, data, plot=plot)
    else:
        maintain_workflow(workflow, code, data, run=True, plot=plot)


@click.command()
@click.argument('workflow')
@click.option('--code', '-c', default=None, help='The path of the code.')
@click.option('--data', '-d', default=None, help='The path of the data.')
@click.option('--api', '-a', default=None, help='The modlule name of the api.')
@click.option('--plot', '-p', is_flag=True, help='Plot the result.')
@log_options
def maintain(workflow, code, data, api, plot):
    """
    Maintain a workflow.
    """
    if api is not None:
        api = importlib.import_module(api)
        set_config_api(api.query_config, api.update_config)
    if code is None:
        code = Path.cwd()
    if data is None:
        data = Path(code) / 'logs'

    code = Path(os.path.expanduser(code))
    data = Path(os.path.expanduser(data))

    maintain_workflow(workflow, code, data, run=False, plot=plot)


cli.add_command(maintain)
cli.add_command(run)
cli.add_command(create)

if __name__ == '__main__':
    cli()
