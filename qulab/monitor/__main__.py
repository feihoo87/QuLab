"""
QuLab Monitor Command Line Interface

This module provides a command-line interface for launching the QuLab monitor.
It allows users to start a standalone monitor window with configurable settings.
"""

import click

from .monitor import Monitor


@click.command(name='monitor')
@click.option('--columns', '-c', default=4, help='Number of columns in the plot grid')
@click.option('--height', '-h', default=400, help='Minimum height of each plot in pixels')
def main(columns: int, height: int):
    """Launch a standalone QuLab monitor window.

    Args:
        columns: Number of columns in the plot grid
        height: Minimum height of each plot in pixels
    """
    monitor = Monitor(number_of_columns=columns, minimum_height=height)
    while monitor.is_alive():
        pass  # Keep the script running while the monitor is active
