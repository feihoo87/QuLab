"""
QuLab Monitor Command Line Interface

This module provides a command-line interface for launching the QuLab monitor.
It allows users to start a standalone monitor server with configurable settings.
"""

import click

from .monitor import MonitorServer


@click.command(name='monitor')
@click.option('--columns', '-c', default=4, help='Number of columns in the plot grid')
@click.option('--height', '-h', default=400, help='Minimum height of each plot in pixels')
@click.option('--address', '-a', default='127.0.0.1', help='Address to bind the server')
@click.option('--port', '-p', default=5555, help='Port to bind the server')
def main(columns: int, height: int, address: str, port: int):
    """Launch a QuLab monitor server.

    Args:
        columns: Number of columns in the plot grid
        height: Minimum height of each plot in pixels
        address: Address to bind the server (default: 127.0.0.1)
        port: Port to bind the server (default: 5555)
    """
    server = MonitorServer(address=address, 
                         port=port,
                         number_of_columns=columns, 
                         minimum_height=height)
    try:
        while True:
            import time
            time.sleep(1)  # Keep the script running while the server is active
    except KeyboardInterrupt:
        print("\nShutting down monitor server...")
