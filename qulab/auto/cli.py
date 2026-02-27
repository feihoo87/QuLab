"""Command-line interface for AutoLab."""

import asyncio
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from qulab.auto import AgentEvent

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
                "[red]Error: LLM configuration required. "
                "Use --config or specify --provider and --model.[/red]"
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
    from pathlib import Path

    from qulab.auto.agent.memory import SessionMemory

    # Use SessionMemory directly without requiring LLM config
    storage_path = Path(storage)
    memory = SessionMemory(storage_path)
    sessions = memory.list_sessions()

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
    from qulab.auto import SkillLoader

    # Create skill loader directly without requiring LLM config
    search_paths = list(skills_path) if skills_path else None
    loader = SkillLoader(search_paths)

    # Get skills by type
    measurements = loader.list_skills("measurement")
    analyses = loader.list_skills("analysis")

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


class AutoLabInteractiveCLI:
    """AutoLab interactive command-line interface."""

    def __init__(self, lab, config: dict):
        self.lab = lab
        self.config = config
        self.current_session_id: str | None = None
        self.is_running = False
        self.event_buffer: list = []

    async def run(self):
        """Run main loop."""
        self.is_running = True
        self._print_banner()
        self._print_help()

        while self.is_running:
            try:
                # Display prompt
                prompt = self._get_prompt()
                user_input = input(prompt).strip()

                if not user_input:
                    continue

                # Handle command
                if user_input.startswith("/"):
                    await self._handle_command(user_input)
                else:
                    # Handle natural language instruction
                    await self._handle_instruction(user_input)

            except KeyboardInterrupt:
                console.print("\n[System] Interrupted, exiting...")
                break
            except EOFError:
                console.print("\n[System] Input ended, exiting...")
                break
            except Exception as e:
                console.print(f"[red][Error] {e}[/red]")

    def _print_banner(self):
        """Print program startup banner."""
        console.print("""
╔══════════════════════════════════════════════════════════════╗
║                    QuLab AutoLab v0.1                        ║
║           Interactive Quantum Experiment System              ║
╚══════════════════════════════════════════════════════════════╝
        """)

    def _print_help(self):
        """Print help information."""
        console.print("""
Available commands:
  /help              Show help information
  /skills            List all available skills
  /sessions          List all sessions
  /history <id>      View history of specified session
  /load <id>         Load specified session to continue
  /config            Show current configuration
  /quit, /exit       Exit program

Enter natural language instructions to start experiments, for example:
  - "Measure Q1 spectroscopy"
  - "Perform resonator power scan"
  - "Analyze the Rabi data"
""")

    def _get_prompt(self) -> str:
        """Get command prompt."""
        if self.current_session_id:
            short_id = self.current_session_id[:8]
            return f"\n[Session:{short_id}] > "
        return "\n[AutoLab] > "

    async def _handle_command(self, cmd: str):
        """Handle command."""
        parts = cmd.split()
        command = parts[0].lower()
        args = parts[1:]

        if command in ("/help", "/h"):
            self._print_help()
        elif command in ("/quit", "/exit", "/q"):
            console.print("[System] Exiting AutoLab")
            self.is_running = False
        elif command == "/skills":
            self._list_skills()
        elif command == "/sessions":
            self._list_sessions()
        elif command == "/history":
            if args:
                self._show_history(args[0])
            else:
                console.print("[red][Error] Usage: /history <session_id>[/red]")
        elif command == "/load":
            if args:
                await self._load_session(args[0])
            else:
                console.print("[red][Error] Usage: /load <session_id>[/red]")
        elif command == "/config":
            self._show_config()
        elif command == "/clear":
            console.print("\n" * 50)
        else:
            console.print(f"[red][Error] Unknown command: {command}[/red]")
            console.print("Enter /help to see available commands")

    def _list_skills(self):
        """List all available skills."""
        console.print("\n=== Available Skills ===")

        measurement_skills = self.lab.list_skills("measurement")
        analysis_skills = self.lab.list_skills("analysis")

        if measurement_skills:
            console.print("\n[Measurement Skills]")
            for name in measurement_skills:
                info = self.lab.get_skill_info(name)
                desc = info.get("description", "No description")
                console.print(f"  • {name}: {desc}")

        if analysis_skills:
            console.print("\n[Analysis Skills]")
            for name in analysis_skills:
                info = self.lab.get_skill_info(name)
                desc = info.get("description", "No description")
                console.print(f"  • {name}: {desc}")

        if not measurement_skills and not analysis_skills:
            console.print("  (No skills available)")

        console.print()

    def _list_sessions(self):
        """List all sessions."""
        sessions = self.lab.list_sessions()
        console.print("\n=== Session List ===")

        if not sessions:
            console.print("  (No sessions)")
            return

        for session in sessions:
            sid = session.get("id", "unknown")[:8]
            created = session.get("created", "unknown")
            messages = len(session.get("messages", []))
            console.print(f"  • {sid}... | Created: {created} | Messages: {messages}")
        console.print()

    def _show_history(self, session_id: str):
        """Show session history."""
        # Try to load session
        sessions = self.lab.list_sessions()
        full_id = None

        for session in sessions:
            if session["id"].startswith(session_id):
                full_id = session["id"]
                break

        if not full_id:
            console.print(f"[red][Error] Session not found: {session_id}[/red]")
            return

        history = self.lab.memory.load_session(full_id)
        if not history:
            console.print(f"[red][Error] Cannot load session: {session_id}[/red]")
            return

        console.print(f"\n=== Session History ({full_id[:16]}...) ===\n")

        for msg in history.get("messages", []):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if role == "user":
                console.print(f"[User] {content[:200]}")
            elif role == "assistant":
                if content:
                    console.print(f"[AI] {content[:200]}")
                tool_calls = msg.get("tool_calls", [])
                for tc in tool_calls:
                    name = tc.get("name", "unknown")
                    args = tc.get("arguments", {})
                    console.print(f"  [Tool] {name}({args})")
            elif role == "tool":
                # Simplify tool result display
                console.print("  [Result] ...")
            console.print()

    async def _load_session(self, session_id: str):
        """Load session to continue."""
        # Try to find full session ID
        sessions = self.lab.list_sessions()
        full_id = None

        for session in sessions:
            if session["id"].startswith(session_id):
                full_id = session["id"]
                break

        if not full_id:
            console.print(f"[red][Error] Session not found: {session_id}[/red]")
            return

        self.current_session_id = full_id
        sid = full_id[:16]
        console.print(f"[System] Loaded session: {sid}...")
        console.print(
            "Enter natural language instructions to continue, or /history to view history"
        )

    async def _handle_instruction(self, instruction: str):
        """Handle natural language instruction."""
        console.print(f"\n[User] {instruction}")
        console.print("-" * 50)

        # Start or continue session
        session_id = self.current_session_id

        try:
            async for event in self.lab.start(instruction, session_id=session_id):
                await self._handle_event(event)

            # Save current session ID
            if self.lab.current_session_id:
                self.current_session_id = self.lab.current_session_id

        except Exception as e:
            console.print(f"[red][Error] Execution failed: {e}[/red]")
            import traceback
            traceback.print_exc()

    async def _handle_event(self, event):
        """Handle Agent event."""
        event_type = event.type

        if event_type == "thinking":
            if self.config.get("enable_thinking", True):
                console.print(f"\n[Thinking] {event.content}")

        elif event_type == "tool_call":
            console.print(f"\n[Execute] {event.tool_name}")
            if event.tool_args:
                # Format arguments
                args_str = ", ".join(f"{k}={v!r}" for k, v in event.tool_args.items())
                console.print(f"       Args: {args_str[:100]}")

        elif event_type == "tool_result":
            result = event.result or {}
            if result.get("success"):
                console.print("[Complete] ✓ Success")
                # Show key results
                if "dataset_id" in result:
                    console.print(f"       Dataset: {result['dataset_id'][:16]}...")
                if "document_id" in result:
                    console.print(f"       Document: {result['document_id'][:16]}...")
            else:
                error = result.get("error", "Unknown error")
                console.print(f"[Failed] ✗ {error}")

        elif event_type == "human_query":
            console.print(f"\n[Query] {event.question}")
            if event.options:
                console.print("       Options:", ", ".join(event.options))

            # Get user response
            response = input("\n[Your answer] ")

            # Resume execution
            async for resume_event in self.lab.respond(response):
                await self._handle_event(resume_event)

        elif event_type == "config_request":
            console.print(f"\n[Config Request] {event.reason}")
            console.print(f"       Updates: {event.updates}")

            # Request confirmation
            confirm = input("Confirm update? (yes/no): ").strip().lower()

            if confirm in ("yes", "y", "是"):
                async for resume_event in self.lab.respond({"approved": True}):
                    await self._handle_event(resume_event)
            else:
                async for resume_event in self.lab.respond({"approved": False, "reason": "User rejected"}):
                    await self._handle_event(resume_event)

        elif event_type == "complete":
            console.print(f"\n[Complete] {event.content}")

        elif event_type == "error":
            console.print(f"\n[Error] {event.content}")

    def _show_config(self):
        """Show current configuration."""
        console.print("\n=== Current Configuration ===")
        llm = self.config.get("llm", {})
        console.print(f"  LLM Provider: {llm.get('provider', 'default')}")
        console.print(f"  Model: {llm.get('model', 'default')}")
        console.print(f"  Storage: {self.config.get('storage', {}).get('path', './autolab_data')}")
        console.print(f"  Max Iterations: {self.config.get('max_iterations', 40)}")
        console.print(f"  Enable Thinking: {self.config.get('enable_thinking', True)}")
        console.print()


def _load_config(config_path: str | None = None) -> dict:
    """Load configuration file.

    Priority:
    1. Passed config_path parameter
    2. AUTOLAB_CONFIG environment variable
    3. Default path ./autolab_config.yaml
    4. ~/.qulab/config.yaml
    5. Default config + environment variables

    Environment variables take priority over config file:
    - KIMI_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY

    Returns:
        Configuration dictionary
    """
    paths = []

    if config_path:
        paths.append(Path(config_path))

    if os.environ.get("AUTOLAB_CONFIG"):
        paths.append(Path(os.environ["AUTOLAB_CONFIG"]))

    paths.extend([
        Path("./autolab_config.yaml"),
        Path.home() / ".qulab" / "config.yaml",
    ])

    config = None
    for path in paths:
        if path.exists():
            console.print(f"[Config] Loading config file: {path}")
            with open(path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            break

    if config is None:
        console.print("[Config] No config file found, using default config")
        config = {"llm": {}}

    # Environment variables take priority over config file
    llm_config = config.get("llm", {})

    if os.environ.get("KIMI_API_KEY"):
        llm_config["provider"] = "openai"
        llm_config["model"] = llm_config.get("model", "kimi-k2.5")
        llm_config["base_url"] = "https://api.moonshot.cn/v1"
        llm_config["api_key"] = os.environ["KIMI_API_KEY"]
    elif os.environ.get("OPENAI_API_KEY"):
        llm_config["provider"] = "openai"
        llm_config["model"] = llm_config.get("model", "gpt-4")
        llm_config["api_key"] = os.environ["OPENAI_API_KEY"]
        if "base_url" in llm_config:
            del llm_config["base_url"]
    elif os.environ.get("ANTHROPIC_API_KEY"):
        llm_config["provider"] = "anthropic"
        llm_config["model"] = llm_config.get("model", "claude-sonnet-4-6")
        llm_config["api_key"] = os.environ["ANTHROPIC_API_KEY"]
        if "base_url" in llm_config:
            del llm_config["base_url"]

    # Ensure default values
    # Kimi model requires temperature=1
    if "temperature" not in llm_config:
        llm_config["temperature"] = 1.0
    if "max_tokens" not in llm_config:
        llm_config["max_tokens"] = 4096

    config["llm"] = llm_config

    # Other default config
    if "storage" not in config:
        config["storage"] = {"type": "local", "path": "./autolab_data"}
    if "max_iterations" not in config:
        config["max_iterations"] = 40

    # For Kimi models, always disable thinking to avoid API errors with tool calls
    model_name = llm_config.get("model", "").lower()
    if "kimi" in model_name:
        config["enable_thinking"] = False
    elif "enable_thinking" not in config:
        config["enable_thinking"] = True

    return config


def _get_storage(config: dict):
    """Create storage instance based on configuration."""
    from qulab.storage import LocalStorage

    storage_config = config.get("storage", {})
    storage_type = storage_config.get("type", "local")
    storage_path = storage_config.get("path", "./autolab_data")

    if storage_type == "local":
        path = Path(storage_path)
        path.mkdir(parents=True, exist_ok=True)
        return LocalStorage(str(path))
    else:
        raise ValueError(f"Unsupported storage type: {storage_type}")


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
def chat(
    storage: str,
    config: str | None,
    provider: str | None,
    model: str | None,
    base_url: str | None,
    api_key: str | None,
):
    """Start interactive chat session for automated experiments."""
    from qulab.auto import AutoLab, AutoLabConfig, LLMConfig
    from qulab.storage import LocalStorage

    async def main():
        # Load config
        config_dict = _load_config(config)

        # Override config with command line options
        if provider:
            config_dict["llm"]["provider"] = provider
        if model:
            config_dict["llm"]["model"] = model
        if base_url:
            config_dict["llm"]["base_url"] = base_url
        if api_key:
            config_dict["llm"]["api_key"] = api_key

        # Override storage path
        config_dict["storage"]["path"] = storage

        # Check API Key
        llm_config = config_dict.get("llm", {})
        if not llm_config.get("api_key"):
            console.print("[red][Error] API Key not set[/red]")
            console.print("Please set one of the following environment variables:")
            console.print("  - KIMI_API_KEY")
            console.print("  - OPENAI_API_KEY")
            console.print("  - ANTHROPIC_API_KEY")
            console.print("Or create config file ./autolab_config.yaml")
            sys.exit(1)

        # Create storage
        storage_instance = _get_storage(config_dict)

        # Create AutoLab instance
        console.print("[System] Initializing AutoLab...")

        try:
            # Build full AutoLabConfig from config_dict
            lab_config = AutoLabConfig.from_dict(config_dict)
            autolab = AutoLab(
                storage=storage_instance,
                config=lab_config,
            )
            console.print(f"[System] Loaded {len(autolab.list_skills())} skills")
        except Exception as e:
            console.print(f"[red][Error] Initialization failed: {e}[/red]")
            import traceback
            traceback.print_exc()
            sys.exit(1)

        # Create and run CLI
        cli = AutoLabInteractiveCLI(autolab, config_dict)
        await cli.run()

    asyncio.run(main())


def register_commands(cli):
    """Register AutoLab commands with the main CLI."""
    cli.add_command(auto_cli)
