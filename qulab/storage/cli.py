"""CLI commands for storage management."""

import json
from pathlib import Path

import click

from qulab.cli.config import get_config_value


@click.group()
def storage():
    """Storage management commands."""
    pass


# Document commands
@storage.group()
def doc():
    """Document operations."""
    pass


@doc.command("create")
@click.argument("name")
@click.argument("data_file", type=click.File("r"), required=False)
@click.option("--tag", "-t", multiple=True, help="Tags to add")
@click.option("--state", "-s", default="unknown", help="Document state")
@click.option("--script", help="Script code or @file path")
@click.option(
    "--data-path",
    "-d",
    default=lambda: str(get_config_value("data", Path, Path.home() / ".qulab" / "storage")),
    help="Storage path",
)
def doc_create(name, data_file, tag, state, script, data_path):
    """Create a new document."""
    from .local import LocalStorage

    storage = LocalStorage(data_path)

    data = {}
    if data_file:
        data = json.load(data_file)

    # Handle script: if starts with @, read from file
    script_code = None
    if script:
        if script.startswith("@"):
            script_path = Path(script[1:])
            script_code = script_path.read_text()
        else:
            script_code = script

    ref = storage.create_document(name, data, state=state, tags=list(tag), script=script_code)
    click.echo(f"Created document {ref.id}: {ref.name}")


@doc.command("get")
@click.argument("id", type=int)
@click.option(
    "--data-path",
    "-d",
    default=lambda: str(get_config_value("data", Path, Path.home() / ".qulab" / "storage")),
    help="Storage path",
)
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
@click.option("--show-script", is_flag=True, help="Show script content")
def doc_get(id, data_path, json_output, show_script):
    """Get a document by ID."""
    from .local import LocalStorage

    storage = LocalStorage(data_path)
    doc = storage.get_document(id)

    if json_output:
        click.echo(json.dumps(doc.to_dict(), indent=2, default=str))
    else:
        click.echo(f"Document {doc.id}: {doc.name}")
        click.echo(f"  State: {doc.state}")
        click.echo(f"  Tags: {', '.join(doc.tags) if doc.tags else 'None'}")
        click.echo(f"  Created: {doc.ctime}")
        if doc.script_hash:
            click.echo(f"  Script Hash: {doc.script_hash}")
            if show_script and doc.script:
                click.echo(f"  Script:\n{doc.script}")
        click.echo(f"  Data: {json.dumps(doc.data, indent=2)}")


@doc.command("query")
@click.option("--name", "-n", help="Name pattern")
@click.option("--tag", "-t", multiple=True, help="Filter by tags")
@click.option("--state", "-s", help="Filter by state")
@click.option("--limit", "-l", default=10, help="Limit results")
@click.option(
    "--data-path",
    "-d",
    default=lambda: str(get_config_value("data", Path, Path.home() / ".qulab" / "storage")),
    help="Storage path",
)
def doc_query(name, tag, state, limit, data_path):
    """Query documents."""
    from .local import LocalStorage

    storage = LocalStorage(data_path)

    results = list(
        storage.query_documents(
            name=name, tags=list(tag) if tag else None, state=state, limit=limit
        )
    )

    if not results:
        click.echo("No documents found.")
        return

    click.echo(f"{'ID':<8} {'Name':<30} {'State':<10} {'Tags'}")
    click.echo("-" * 70)
    for ref in results:
        doc = ref.get()
        tags_str = ", ".join(doc.tags) if doc.tags else "None"
        click.echo(f"{doc.id:<8} {doc.name:<30} {doc.state:<10} {tags_str}")


@doc.command("delete")
@click.argument("id", type=int)
@click.option(
    "--data-path",
    "-d",
    default=lambda: str(get_config_value("data", Path, Path.home() / ".qulab" / "storage")),
    help="Storage path",
)
@click.confirmation_option(prompt="Are you sure you want to delete this document?")
def doc_delete(id, data_path):
    """Delete a document."""
    from .local import DocumentRef, LocalStorage

    storage = LocalStorage(data_path)
    ref = DocumentRef(id, storage)
    if ref.delete():
        click.echo(f"Deleted document {id}")
    else:
        click.echo(f"Document {id} not found")


# Dataset commands
@storage.group()
def dataset():
    """Dataset operations."""
    pass


@dataset.command("create")
@click.argument("name")
@click.option("--desc", "-d", help="Description JSON string")
@click.option("--config", "-c", help="Config JSON string")
@click.option("--script", "-s", help="Script code or @file path")
@click.option(
    "--data-path",
    default=lambda: str(get_config_value("data", Path, Path.home() / ".qulab" / "storage")),
    help="Storage path",
)
def dataset_create(name, desc, config, script, data_path):
    """Create a new dataset."""
    from .local import LocalStorage

    storage = LocalStorage(data_path)
    description = json.loads(desc) if desc else {}
    config_dict = json.loads(config) if config else None

    # Handle script: if starts with @, read from file
    script_code = None
    if script:
        if script.startswith("@"):
            script_path = Path(script[1:])
            script_code = script_path.read_text()
        else:
            script_code = script

    ref = storage.create_dataset(name, description, config=config_dict, script=script_code)
    click.echo(f"Created dataset {ref.id}: {ref.name}")


@dataset.command("info")
@click.argument("id", type=int)
@click.option(
    "--data-path",
    default=lambda: str(get_config_value("data", Path, Path.home() / ".qulab" / "storage")),
    help="Storage path",
)
@click.option("--show-config", is_flag=True, help="Show config content")
@click.option("--show-script", is_flag=True, help="Show script content")
def dataset_info(id, data_path, show_config, show_script):
    """Show dataset info."""
    from .local import LocalStorage

    storage = LocalStorage(data_path)
    ds = storage.get_dataset(id)
    click.echo(f"Dataset {ds.id}: {ds.name}")
    click.echo(f"  Keys: {', '.join(ds.keys()) if ds.keys() else 'None'}")
    click.echo(f"  Description: {json.dumps(ds.description, indent=2)}")

    if ds.config_hash:
        click.echo(f"  Config Hash: {ds.config_hash}")
        if show_config and ds.config:
            click.echo(f"  Config: {json.dumps(ds.config, indent=2)}")
    if ds.script_hash:
        click.echo(f"  Script Hash: {ds.script_hash}")
        if show_script and ds.script:
            click.echo(f"  Script:\n{ds.script}")


@dataset.command("query")
@click.option("--name", "-n", help="Name pattern")
@click.option("--tag", "-t", multiple=True, help="Filter by tags")
@click.option("--limit", "-l", default=10, help="Limit results")
@click.option(
    "--data-path",
    default=lambda: str(get_config_value("data", Path, Path.home() / ".qulab" / "storage")),
    help="Storage path",
)
def dataset_query(name, tag, limit, data_path):
    """Query datasets."""
    from .local import LocalStorage

    storage = LocalStorage(data_path)

    results = list(
        storage.query_datasets(
            name=name, tags=list(tag) if tag else None, limit=limit
        )
    )

    if not results:
        click.echo("No datasets found.")
        return

    click.echo(f"{'ID':<8} {'Name':<30} {'Keys'}")
    click.echo("-" * 50)
    for ref in results:
        ds = ref.get()
        keys_str = ", ".join(ds.keys()) if ds.keys() else "None"
        click.echo(f"{ds.id:<8} {ds.name:<30} {keys_str}")


@dataset.command("delete")
@click.argument("id", type=int)
@click.option(
    "--data-path",
    default=lambda: str(get_config_value("data", Path, Path.home() / ".qulab" / "storage")),
    help="Storage path",
)
@click.confirmation_option(prompt="Are you sure you want to delete this dataset?")
def dataset_delete(id, data_path):
    """Delete a dataset."""
    from .local import DatasetRef, LocalStorage

    storage = LocalStorage(data_path)
    ref = DatasetRef(id, storage)
    if ref.delete():
        click.echo(f"Deleted dataset {id}")
    else:
        click.echo(f"Dataset {id} not found")


# Server commands
@storage.group()
def server():
    """Storage server operations."""
    pass


@server.command("start")
@click.option("--host", "-h", default="127.0.0.1", help="Server host")
@click.option("--port", "-p", default=6789, help="Server port")
@click.option(
    "--data-path",
    "-d",
    default=lambda: str(get_config_value("data", Path, Path.home() / ".qulab" / "storage")),
    help="Storage path",
)
def server_start(host, port, data_path):
    """Start storage server."""
    import asyncio

    from .local import LocalStorage
    from .server import StorageServer

    storage = LocalStorage(data_path)
    srv = StorageServer(storage, host=host, port=port)
    click.echo(f"Starting storage server on {host}:{port}")
    click.echo(f"Data path: {data_path}")
    click.echo("Press Ctrl+C to stop")

    try:
        asyncio.run(srv.run())
    except KeyboardInterrupt:
        click.echo("\nShutting down...")


@server.command("status")
@click.option("--host", "-h", default="127.0.0.1", help="Server host")
@click.option("--port", "-p", default=6789, help="Server port")
def server_status(host, port):
    """Check server status."""
    from .remote import RemoteStorage

    try:
        remote = RemoteStorage(f"tcp://{host}:{port}", timeout=5.0)
        # Try a simple count operation
        count = remote.count_documents()
        click.echo(f"Server is running at {host}:{port}")
        click.echo(f"Documents: {count}")
    except Exception as e:
        click.echo(f"Server is not responding: {e}")


# Main entry point
@click.group()
def main():
    """Storage CLI."""
    pass


main.add_command(storage)

if __name__ == "__main__":
    main()
