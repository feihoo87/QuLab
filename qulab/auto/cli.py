"""Command-line interface for AutoLab."""

import asyncio
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.group(name="auto")
def auto_cli():
    """AutoLab - Automated Experiment Framework."""
    pass


@auto_cli.command()
@click.option(
    "--storage",
    "-s",
    type=click.Path(),
    default="./autolab_data",
    help="Storage path",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Config file path",
)
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["openai", "anthropic"]),
    help="LLM provider",
)
@click.option("--model", "-m", help="Model name")
@click.option("--base-url", "-u", help="API base URL")
@click.option("--api-key", "-k", help="API key")
@click.argument("instruction", required=True)
def run(
    storage: str,
    config: str | None,
    provider: str | None,
    model: str | None,
    base_url: str | None,
    api_key: str | None,
    instruction: str,
):
    """Run an automated experiment session."""
    from qulab.auto import AutoLab, AutoLabConfig, LLMConfig
    from qulab.storage import LocalStorage

    async def main():
        # Load or build config
        if config:
            lab_config = AutoLabConfig.from_file(config)
        else:
            # Build LLM config from options
            llm_config = None
            if provider and model:
                llm_config = LLMConfig(
                    provider=provider,
                    model=model,
                    base_url=base_url,
                    api_key=api_key,
                )
            lab_config = AutoLabConfig(llm=llm_config)

        if not lab_config.llm:
            console.print(
                "[red]Error: LLM configuration required. Use --config or specify --provider and --model."
            )
            return

        # Initialize storage and lab
        storage_instance = LocalStorage(storage)
        lab = AutoLab(storage_instance, config=lab_config)

        # Run session
        console.print(Panel(f"Starting session: {instruction}", title="AutoLab"))

        async for event in lab.start(instruction):
            if event.type == "thinking":
                console.print(f"[dim]🤔 {event.content}[/dim]")
            elif event.type == "tool_call":
                console.print(f"[cyan]🛠️  {event.tool_name}({event.tool_args})[/cyan]")
            elif event.type == "tool_result":
                console.print(f"[green]✓ Result: {event.result}[/green]")
            elif event.type == "complete":
                console.print(Panel(event.content or "Done", title="Complete"))
            elif event.type == "error":
                console.print(f"[red]❌ Error: {event.content}[/red]")
            elif event.type == "human_query":
                console.print(f"[yellow]❓ {event.question}[/yellow]")
                # In CLI mode, ask for input
                response = click.prompt("Your response")
                async for resp_event in lab.respond(response):
                    console.print(f"[dim]{resp_event.type}: {resp_event.content}[/dim]")

    asyncio.run(main())


@auto_cli.command()
@click.option(
    "--storage",
    "-s",
    type=click.Path(),
    default="./autolab_data",
    help="Storage path",
)
def list_sessions(storage: str):
    """List all sessions."""
    from qulab.auto import AutoLab, AutoLabConfig
    from qulab.storage import LocalStorage

    storage_instance = LocalStorage(storage)
    lab = AutoLab(storage_instance, config=AutoLabConfig())

    sessions = lab.list_sessions()

    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return

    table = Table(title="Sessions")
    table.add_column("Session ID")
    table.add_column("Created At")

    for session in sessions:
        table.add_row(
            session.get("session_id", "unknown"),
            session.get("created_at", "unknown"),
        )

    console.print(table)


@auto_cli.command()
@click.option(
    "--skills-path",
    "-p",
    type=click.Path(exists=True),
    multiple=True,
    help="Additional paths to search for skills",
)
def list_skills(skills_path: tuple[str, ...]):
    """List available skills."""
    from qulab.auto import AutoLab, AutoLabConfig
    from qulab.storage import LocalStorage

    lab = AutoLab(
        LocalStorage("./tmp"),
        config=AutoLabConfig(),
        skills_path=list(skills_path) if skills_path else None,
    )

    measurements = lab.list_skills("measurement")
    analyses = lab.list_skills("analysis")

    if measurements:
        console.print(Panel(
            "\n".join(f"• {m}" for m in measurements),
            title="Measurement Skills",
        ))

    if analyses:
        console.print(Panel(
            "\n".join(f"• {a}" for a in analyses),
            title="Analysis Skills",
        ))

    if not measurements and not analyses:
        console.print("[dim]No skills found.[/dim]")


@auto_cli.command()
@click.argument("path", type=click.Path())
def init_config(path: str):
    """Create a sample configuration file."""
    config = {
        "llm": {
            "provider": "openai",
            "base_url": "https://api.moonshot.cn/v1",
            "api_key": "your-api-key-here",
            "model": "kimi-k2.5",
            "temperature": 0.7,
            "max_tokens": 4096,
        },
        "skills_paths": ["./skills"],
        "max_iterations": 40,
        "enable_thinking": True,
    }

    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    console.print(f"[green]Created config file: {config_path}[/green]")


def register_commands(cli):
    """Register AutoLab commands with the main CLI."""
    cli.add_command(auto_cli)
