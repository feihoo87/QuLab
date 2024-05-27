import click

from .monitor.__main__ import main as monitor
from .scan.recorder import record
from .scan.server import server
from .sys.net.cli import dht
from .visualization.__main__ import plot


@click.group()
def main():
    pass


@main.command()
def hello():
    """Print hello world."""
    click.echo('hello, world')


main.add_command(monitor)
main.add_command(plot)
main.add_command(dht)
main.add_command(record)
main.add_command(server)

if __name__ == '__main__':
    main()
