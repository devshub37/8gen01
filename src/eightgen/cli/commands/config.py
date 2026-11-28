"""CLI config and diagnostic command."""

import asyncio
from pathlib import Path
import click
from rich.table import Table
from eightgen.cli.display import console, print_banner, print_status, print_error, print_success
from eightgen.config.loader import get_settings
from eightgen.core.agent import Agent


@click.group(name="config")
def config_cmd() -> None:
    """View and verify 8Gen configuration, Gemini API, and Ollama."""
    pass


@config_cmd.command(name="show")
def show_config() -> None:
    """Display current active configuration."""
    print_banner()
    settings = get_settings()

    table = Table(title="🔧 Active Settings", border_style="cyan")
    table.add_column("Key", style="bold cyan")
    table.add_column("Value", style="white")

    active_provider = settings.resolved_provider
    table.add_row("Active Provider", f"[bold green]{active_provider.upper()}[/bold green]")
    if active_provider == "gemini":
        key_masked = f"{settings.gemini_api_key[:6]}...{settings.gemini_api_key[-4:]}" if len(settings.gemini_api_key) > 10 else "[red]Not configured[/red]"
        table.add_row("Gemini Model", settings.gemini_model)
        table.add_row("Gemini API Key", key_masked)
        table.add_row("Gemini Proxy", settings.gemini_proxy_url or "[dim]Direct Google API[/dim]")
    else:
        table.add_row("Ollama URL", settings.ollama_url)
        table.add_row("Ollama Model", settings.model)

    table.add_row("Temperature", str(settings.temperature))
    table.add_row("Output Directory", str(settings.output_dir.resolve()))
    table.add_row("Database Path", str(settings.db_path.resolve()))
    table.add_row("Web Server", f"http://{settings.server_host}:{settings.server_port}")

    console.print(table)


@config_cmd.command(name="set-key")
@click.argument("key", type=str)
def set_key(key: str) -> None:
    """Save Gemini API Key to local .env configuration."""
    clean_key = key.strip()
    env_file = Path("./.env")
    lines = []
    if env_file.exists():
        lines = env_file.read_text().splitlines()

    updated = False
    new_lines = []
    for line in lines:
        if line.startswith("EIGHTGEN_GEMINI_API_KEY=") or line.startswith("GEMINI_API_KEY="):
            new_lines.append(f"GEMINI_API_KEY={clean_key}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f"GEMINI_API_KEY={clean_key}")
        new_lines.append("EIGHTGEN_PROVIDER=gemini")

    env_file.write_text("\n".join(new_lines) + "\n")
    print_success("Gemini API key saved successfully in .env!")
    console.print("[dim]8Gen will now use Google Gemini for ultra-fast generation.[/dim]")


@config_cmd.command(name="check")
def check_config() -> None:
    """Diagnose AI Provider (Gemini or Ollama) connectivity."""
    print_banner()
    settings = get_settings()
    active_provider = settings.resolved_provider
    try:
        agent = Agent(settings)
    except ValueError as exc:
        print_error(f"Configuration error: {exc}")
        return

    async def _check():
        print_status(f"Testing active provider: [bold cyan]{active_provider.upper()}[/bold cyan]...")
        health = await agent.check_health()
        if health.get("connected"):
            print_success(f"Provider '{active_provider}' is connected and ready!")
            console.print(f"  ★ Model: [cyan]{health.get('configured_model')}[/cyan]")
        else:
            print_error(f"Provider '{active_provider}' is not reachable or not configured.")
            if active_provider == "gemini":
                console.print("\n[yellow]To use Gemini (100x faster, high quality games):[/yellow]")
                console.print("1. Get a free API key at [bold cyan]https://aistudio.google.com/[/bold cyan]")
                console.print("2. Run: [bold]8gen config set-key YOUR_GEMINI_KEY[/bold]")
                console.print("   or set: [bold]export GEMINI_API_KEY=YOUR_KEY[/bold]")
            else:
                console.print(f"[dim]Make sure Ollama is running at {settings.ollama_url}[/dim]")

    asyncio.run(_check())
