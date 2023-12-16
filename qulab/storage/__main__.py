import click


@click.command()
@click.option('--executor', default='', help='Executor address to use.')
@click.option('--port', default=8080, help='Port to run the server on.')
@click.option('--host', default='127.0.0.1', help='Host to run the server on.')
@click.option('--db-url', default=None, help='Database URL to use.')
@click.option('--data-path',
              default='waveforms/data',
              help='Path to the data directory.')
@click.option('--debug', is_flag=True, help='Run in debug mode.')
@click.option('--workers',
              default=1,
              help='Number of workers to run the server with.')
@click.option('--timeout', default=60, help='Timeout for requests.')
@click.option('--log-level',
              default='INFO',
              help='Log level to run the server with.')
@click.option('--log-file',
              default='/var/log/waveforms/server.log',
              help='Log file to run the server with.')
@click.option('--log-format',
              default='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
              help='Log format to run the server with.')
def main(executor, port, host, db_url, data_path, debug, workers, timeout,
         log_level, log_file, log_format):
    """
    Main entry point for the server.
    """
    from waveforms.server import create_app

    app = create_app(
        executor=executor,
        port=port,
        host=host,
        db_url=db_url,
        data_path=data_path,
        debug=debug,
        workers=workers,
        timeout=timeout,
        log_level=log_level,
        log_file=log_file,
        log_format=log_format,
    )
    app.run()


if __name__ == '__main__':
    main()
    