"""CLI commands for the trace system.

Provides ``qulab trace serve``, ``qulab trace export``,
``qulab trace status``, and ``qulab trace upload-buffer`` commands.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import click


def _default_data_path() -> str:
    return str(Path.home() / ".qulab" / "trace" / "data")


def _default_buffer_dir() -> str:
    return str(Path.home() / ".qulab" / "trace" / "buffer")


@click.group("trace")
def trace_cli() -> None:
    """Notebook behavior tracking for ML training."""


@trace_cli.command("serve")
@click.option("--host", "-h", default="127.0.0.1", help="Server bind address.")
@click.option("--port", "-p", default=8790, type=int, help="Server port.")
@click.option(
    "--data-path",
    "-d",
    default=_default_data_path,
    help="Data storage directory.",
)
def serve(host: str, port: int, data_path: str) -> None:
    """Start the trace collection server."""
    import uvicorn

    from .server import create_app

    data = Path(data_path)
    data.mkdir(parents=True, exist_ok=True)

    # Create the app so we can log the config
    app = create_app(data)

    click.echo(f"Starting trace server on {host}:{port}")
    click.echo(f"Data path: {data}")
    click.echo("Press Ctrl+C to stop")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


@trace_cli.command("export")
@click.option(
    "--data-path",
    "-d",
    default=_default_data_path,
    help="Data storage directory (for local export).",
)
@click.option(
    "--output",
    "-o",
    default="-",
    help="Output file path. Use '-' for stdout.",
)
@click.option(
    "--session-id",
    "-s",
    multiple=True,
    help="Filter by session ID (repeatable).",
)
@click.option("--after", help="Events after this ISO datetime.")
@click.option("--before", help="Events before this ISO datetime.")
def export(
    data_path: str,
    output: str,
    session_id: tuple,
    after: str,
    before: str,
) -> None:
    """Export trace data for ML training as JSONL."""
    from .storage import TraceStore

    store = TraceStore(Path(data_path))
    session_ids = list(session_id) if session_id else None

    traces = store.export_training_data(
        session_ids=session_ids, after=after, before=before
    )
    store.close()

    if not traces:
        click.echo("No matching sessions found.", err=True)
        return

    if output == "-":
        for trace in traces:
            sys.stdout.write(json.dumps(trace, ensure_ascii=False) + "\n")
        click.echo(f"Exported {len(traces)} session(s)", err=True)
    else:
        with open(output, "w", encoding="utf-8") as out:
            for trace in traces:
                out.write(json.dumps(trace, ensure_ascii=False) + "\n")
        click.echo(
            f"Exported {len(traces)} session(s) to {output}", err=True
        )


@trace_cli.command("status")
@click.option("--host", "-h", default="127.0.0.1", help="Server host.")
@click.option("--port", "-p", default=8790, type=int, help="Server port.")
def status(host: str, port: int) -> None:
    """Check trace server status."""
    url = f"http://{host}:{port}/api/v1/status"
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (URLError, OSError) as exc:
        click.echo(f"Server unreachable at {host}:{port}: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Server: http://{host}:{port}")
    click.echo(f"Status: {data.get('status', 'unknown')}")
    click.echo(f"Sessions: {data.get('total_sessions', 0)}")
    click.echo(f"Events: {data.get('total_events', 0)}")
    click.echo(f"JSONL files: {data.get('jsonl_files', 0)}")
    size_mb = data.get("total_size_bytes", 0) / (1024 * 1024)
    click.echo(f"Storage size: {size_mb:.2f} MB")
    click.echo(f"Data path: {data.get('data_path', '')}")


@trace_cli.command("upload-buffer")
@click.option(
    "--buffer-dir",
    default=_default_buffer_dir,
    help="Local buffer directory.",
)
@click.option(
    "--server-url",
    default="http://127.0.0.1:8790",
    help="Trace server URL.",
)
def upload_buffer(buffer_dir: str, server_url: str) -> None:
    """Upload locally buffered events to the server.

    Use this to retroactively upload events from sessions where
    the server was not reachable.
    """
    from .client import upload_buffer_files

    buf_path = Path(buffer_dir)
    if not buf_path.exists():
        click.echo(f"Buffer directory does not exist: {buf_path}", err=True)
        return

    click.echo(f"Scanning {buf_path} for pending uploads...")
    results = upload_buffer_files(buf_path, server_url)

    if not results:
        click.echo("No pending events to upload.")
        return

    total = sum(results.values())
    click.echo(f"Uploaded {total} events from {len(results)} file(s):")
    for filename, count in results.items():
        click.echo(f"  {filename}: {count} events")
