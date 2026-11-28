"""Interactive beginner-friendly CLI wizard."""

import asyncio
import click
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table

from eightgen.cli.display import (
    console,
    print_banner,
    print_game_card,
    print_error,
    print_status,
    print_success,
)
from eightgen.config.loader import get_settings
from eightgen.core.agent import Agent
from eightgen.utils.browser import open_in_browser


PRESET_GAMES = [
    {
        "title": "Neon Space Shooter",
        "category": "shooter",
        "prompt": "Retro arcade space shooter with laser cannons, alien waves, explosion sound effects, and score tracking",
        "icon": "🚀",
    },
    {
        "title": "Cyberpunk Snake",
        "category": "arcade",
        "prompt": "Classic retro snake game with neon glowing trails, collectible fruit bonuses, speed increases, and retro sounds",
        "icon": "🐍",
    },
    {
        "title": "Retro Brick Breaker",
        "category": "arcade",
        "prompt": "Breakout brick breaker game with colorful destructible blocks, bouncing ball, paddle controls, and multiball powerups",
        "icon": "🧱",
    },
    {
        "title": "Flappy Neon Drone",
        "category": "arcade",
        "prompt": "Flappy bird style endless runner navigating electric neon gates with gravity, score counter, and tap/space controls",
        "icon": "⚡",
    },
    {
        "title": "Arcade Pong vs AI",
        "category": "arcade",
        "prompt": "2-player retro Pong with smooth AI opponent, ball speed acceleration, particle effects, and sound effects",
        "icon": "🏓",
    },
    {
        "title": "Gem Match-3 Puzzle",
        "category": "puzzle",
        "prompt": "Match-3 color gem swapping puzzle game with combos, move counter, and sparkling visual effects",
        "icon": "💎",
    },
]


def run_interactive_wizard() -> None:
    """Run interactive zero-friction beginner wizard."""
    print_banner()

    console.print(
        Panel(
            "[bold white]Welcome to 8Gen![/bold white]\n"
            "[dim]This wizard will guide you to create and play your first game in seconds.[/dim]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    settings = get_settings()
    agent = Agent(settings)

    console.print("\n[bold cyan]What would you like to do?[/bold cyan]")
    console.print("  [bold green]1)[/bold green] 🎮 [bold]Create a new game[/bold] (pick a preset or type an idea)")
    console.print("  [bold green]2)[/bold green] 🌐 [bold]Open the Web Studio[/bold] (visual arcade gallery in your browser)")
    console.print("  [bold green]3)[/bold green] 🕹️  [bold]Play existing games[/bold] (browse your library)")
    console.print("  [bold green]4)[/bold green] 🔧 [bold]Check Ollama setup[/bold] (diagnostic check)")
    console.print("  [bold green]5)[/bold green] 🚪 [bold]Exit[/bold]\n")

    choice = Prompt.ask("Choose an option", choices=["1", "2", "3", "4", "5"], default="1")

    if choice == "1":
        _wizard_create_game(agent)
    elif choice == "2":
        _wizard_launch_web(settings)
    elif choice == "3":
        _wizard_browse_games(agent)
    elif choice == "4":
        _wizard_check_ollama(agent)
    else:
        console.print("[dim]Goodbye! Happy game making! 🎮[/dim]")


def _wizard_create_game(agent: Agent) -> None:
    """Guide user through creating a game."""
    console.print("\n[bold yellow]Choose a game template or type your own idea:[/bold yellow]")

    for idx, preset in enumerate(PRESET_GAMES, 1):
        console.print(f"  [bold cyan]{idx})[/bold cyan] {preset['icon']} [bold]{preset['title']}[/bold] [dim]({preset['category']})[/dim]")
    console.print("  [bold cyan]7)[/bold cyan] ✍️  [bold]Custom Game[/bold] (describe anything you want!)\n")

    game_choice = Prompt.ask("Choose a game", choices=["1", "2", "3", "4", "5", "6", "7"], default="1")

    if game_choice == "7":
        prompt = Prompt.ask("\n[bold green]Describe your game idea in simple words[/bold green]")
        category = Prompt.ask("Category (optional)", default="arcade")
    else:
        preset = PRESET_GAMES[int(game_choice) - 1]
        prompt = preset["prompt"]
        category = preset["category"]
        console.print(f"\n[green]Selected:[/green] [bold]{preset['icon']} {preset['title']}[/bold]")

    # Optional customization questions
    include_sound = Confirm.ask("Include retro sound effects?", default=True)
    if include_sound and "sound" not in prompt.lower():
        prompt += ", include Web Audio API retro sound effects"

    style = Prompt.ask(
        "Visual style",
        choices=["Neon Cyberpunk", "8-Bit Retro Pixel", "Modern Minimalist", "Default"],
        default="Default",
    )
    if style != "Default":
        prompt += f", with a {style} visual aesthetic"

    console.print("\n[bold cyan]🚀 Ready to build your game![/bold cyan]")
    console.print(f"[dim]Engine: Ollama ({agent.settings.model})[/dim]")

    async def _generate():
        with console.status("[bold green]Synthesizing your game with local AI... (this usually takes 10-25 seconds)", spinner="dots"):
            try:
                game = await agent.create_game(
                    prompt=prompt,
                    category=category,
                    auto_open=True,
                )
            except Exception as e:
                print_error(f"Generation failed: {e}")
                console.print("\n[dim]Tip: Make sure Ollama is running (`ollama serve` or open the Ollama app).[/dim]")
                return

        print_game_card(game)
        print_success("Game created successfully and opened in your browser!")
        console.print("[dim]You can refine this game anytime by running: [bold]8gen refine last \"your changes\"[/bold][/dim]")

    asyncio.run(_generate())


def _wizard_launch_web(settings) -> None:
    """Launch web dashboard directly."""
    url = f"http://{settings.server_host}:{settings.server_port}"
    print_status(f"Starting Visual Web Studio at [bold cyan]{url}[/bold cyan]")

    import threading
    import time
    import uvicorn

    def _opener():
        time.sleep(0.8)
        open_in_browser(url)

    threading.Thread(target=_opener, daemon=True).start()

    uvicorn.run(
        "eightgen.server.app:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
        log_level="warning",
    )


def _wizard_browse_games(agent: Agent) -> None:
    """Browse games and let user play any by typing its ID."""
    games = agent.list_games(limit=20)
    if not games:
        console.print("\n[dim yellow]No games found in your library yet! Let's make one.[/dim yellow]")
        if Confirm.ask("Create a game now?", default=True):
            _wizard_create_game(agent)
        return

    table = Table(title="Your Games Library", border_style="cyan")
    table.add_column("#", justify="right", style="cyan")
    table.add_column("ID", style="dim")
    table.add_column("Title", style="bold white")
    table.add_column("Version", justify="center")
    table.add_column("Category", style="yellow")

    for i, g in enumerate(games, 1):
        table.add_row(str(i), g.id, g.title, f"v{g.current_version}", g.category)

    console.print(table)
    play_choice = Prompt.ask("\nEnter game number to play (or 'q' to quit)", default="1")
    if play_choice.lower() != "q":
        try:
            idx = int(play_choice) - 1
            if 0 <= idx < len(games):
                selected = games[idx]
                open_in_browser(selected.file_path)
                print_success(f"Opened '{selected.title}' in your browser!")
        except ValueError:
            pass


def _wizard_check_ollama(agent: Agent) -> None:
    """Friendly Ollama diagnostic."""
    async def _check():
        print_status("Checking local Ollama status...")
        health = await agent.check_health()
        if health["ollama_connected"]:
            print_success(f"Ollama is running properly at {health['ollama_url']}")
            models = health.get("available_models", [])
            if models:
                console.print(f"[bold green]✔ Available AI Models ({len(models)}):[/bold green]")
                for m in models:
                    console.print(f"   • [cyan]{m}[/cyan]")
            else:
                console.print("\n[yellow]No models found yet! Run this command to get one:[/yellow]")
                console.print("   [bold]ollama pull qwen2.5-coder:7b[/bold]")
        else:
            print_error(f"Cannot reach Ollama at {health['ollama_url']}")
            console.print("\n[yellow]How to fix:[/yellow]")
            console.print("1. Open your terminal or terminal app")
            console.print("2. Run: [bold]ollama serve[/bold] (or launch the Ollama desktop app)")
            console.print("3. Try running 8Gen again!")

    asyncio.run(_check())


@click.command(name="wizard")
def wizard_cmd() -> None:
    """Launch the friendly interactive game creation wizard."""
    run_interactive_wizard()
