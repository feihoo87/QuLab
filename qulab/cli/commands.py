import click

from ..executor.cli import boot, create, get, maintain, reproduce, run, set
from ..monitor.__main__ import main as monitor
from ..scan.server import server
from ..sys.net.cli import dht
from ..visualization.__main__ import plot


@click.group()
def cli():
    pass


@cli.command()
def hello():
    """Print hello world."""
    click.echo('hello, world')


cli.add_command(monitor)
cli.add_command(plot)
cli.add_command(dht)
cli.add_command(server)
cli.add_command(maintain)
cli.add_command(run)
cli.add_command(reproduce)
cli.add_command(create)
cli.add_command(set)
cli.add_command(get)
cli.add_command(boot)
