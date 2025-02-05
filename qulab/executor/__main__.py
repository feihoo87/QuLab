import importlib
from pathlib import Path

import click

from .load import find_unreferenced_workflows
from .schedule import maintain as maintain_workflow, run as run_workflow
from .transform import set_config_api
from .utils import workflow_template


@click.group()
def cli():
    pass


@click.command()
@click.argument('workflow')
@click.option('--code', '-c', default=None)
def create(workflow, code):
    """
    Create a new workflow file.
    """
    if code is None:
        code = Path.cwd()

    fname = Path(code) / f'{workflow}.py'
    if fname.exists():
        click.echo(f'{workflow}.py already exists')
        return

    fname.parent.mkdir(parents=True, exist_ok=True)
    deps = find_unreferenced_workflows(code)

    with open(fname, 'w') as f:
        f.write(workflow_template(list(deps)))
    click.echo(f'{workflow}.py created')


@click.command()
@click.argument('workflow')
@click.option('--code', '-c', default=None)
@click.option('--data', '-d', default=None)
@click.option('--api', '-g', default=None)
@click.option('--no-dependents', '-n', is_flag=True)
def run(workflow, code, data, api, no_dependents):
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

    if no_dependents:
        run_workflow(workflow, code, data)
    else:
        maintain_workflow(workflow, code, data, run=True)


@click.command()
@click.argument('workflow')
@click.option('--code', '-c', default=None)
@click.option('--data', '-d', default=None)
@click.option('--api', '-g', default=None)
def maintain(workflow, code, data, api):
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

    maintain_workflow(workflow, code, data, run=False)


cli.add_command(maintain)
cli.add_command(run)
cli.add_command(create)

if __name__ == '__main__':
    cli()
