import click

from ..executor.cli import (boot, create, export, get, load, maintain, delete,
                            reproduce, run, set)
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


@cli.group()
def reg():
    """Regestry operations."""
    pass


cli.add_command(monitor)
cli.add_command(plot)
cli.add_command(dht)
cli.add_command(server)
cli.add_command(maintain)
cli.add_command(run)
cli.add_command(reproduce)
cli.add_command(create)
reg.add_command(set)
reg.add_command(get)
reg.add_command(delete)
reg.add_command(load)
reg.add_command(export)
cli.add_command(boot)
