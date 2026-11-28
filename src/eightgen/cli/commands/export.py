"""CLI export command."""

from pathlib import Path
from typing import Optional
import click
from eightgen.cli.display import print_banner, print_error, print_success
from eightgen.config.loader import get_settings
from eightgen.core.agent import Agent


@click.command(name="export")
@click.argument("game_id", type=str)
@click.option("--output", "-o", type=click.Path(), default=None, help="Target file or directory path")
def export_cmd(game_id: str, output: Optional[str]) -> None:
    """Export a self-contained game HTML file to a target destination."""
    print_banner()
    settings = get_settings()
    agent = Agent(settings)

    target_path = Path(output) if output else Path.cwd()

    try:
        exported_file = agent.export_game(game_id, target_path)
        print_success(f"Game exported successfully to: [bold cyan]{exported_file}[/bold cyan]")
    except Exception as e:
        print_error(f"Export failed: {e}")
