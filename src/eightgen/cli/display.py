"""Rich terminal output formatting and display helpers."""

from typing import List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from eightgen.storage.models import Game

console = Console()


def print_banner() -> None:
    """Print stylish 8Gen banner."""
    banner_text = Text()
    banner_text.append("⚡ 8Gen ", style="bold cyan")
    banner_text.append("— Instant AI Game Studio (Local Ollama Engine)\n", style="bold white")
    banner_text.append("Crafting fully playable HTML5 games locally in seconds", style="dim italic")
    console.print(Panel(banner_text, border_style="cyan", padding=(0, 2)))


def print_game_card(game: Game) -> None:
    """Print detailed card for a single game."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold cyan", justify="right")
    table.add_column(style="white")

    table.add_row("Game ID:", game.id)
    table.add_row("Title:", f"[bold green]{game.title}[/bold green]")
    table.add_row("Version:", f"v{game.current_version}")
    table.add_row("Category:", game.category)
    table.add_row("Path:", str(game.file_path))
    table.add_row("Versions:", str(len(game.versions)))
    table.add_row("Updated:", game.updated_at.strftime("%Y-%m-%d %H:%M:%S UTC"))

    panel = Panel(
        table,
        title=f"🎮 [bold yellow]{game.title}[/bold yellow]",
        border_style="green",
        padding=(1, 2),
    )
    console.print(panel)


def print_games_table(games: List[Game]) -> None:
    """Print list of games in a clean table format."""
    if not games:
        console.print("[dim yellow]No games generated yet. Try running: [bold]8gen generate \"space shooter\"[/bold][/dim yellow]")
        return

    table = Table(
        title="🎮 Generated Games Library",
        border_style="cyan",
        header_style="bold magenta",
        show_lines=True,
    )
    table.add_column("ID", style="bold cyan", width=10)
    table.add_column("Title", style="bold white", width=25)
    table.add_column("Ver", justify="center", width=5)
    table.add_column("Category", style="yellow", width=12)
    table.add_column("File", style="dim", overflow="ellipsis")
    table.add_column("Updated", style="dim green", width=20)

    for g in games:
        table.add_row(
            g.id,
            g.title,
            f"v{g.current_version}",
            g.category,
            str(g.file_path.name),
            g.updated_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


def print_status(message: str, style: str = "bold cyan") -> None:
    """Print an informational status message."""
    console.print(f"[{style}]ℹ {message}[/{style}]")


def print_success(message: str) -> None:
    """Print a success status message."""
    console.print(f"[bold green]✔ {message}[/bold green]")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[bold red]✖ {message}[/bold red]")
