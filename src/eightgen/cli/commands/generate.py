"""CLI generate command."""

import asyncio
from typing import Optional
import click

from eightgen.cli.display import console, print_banner, print_game_card, print_error, print_status
from eightgen.config.loader import get_settings
from eightgen.core.agent import Agent


@click.command(name="generate")
@click.argument("prompt", type=str)
@click.option("--category", "-c", type=str, default=None, help="Game category (arcade, platformer, puzzle, etc.)")
@click.option("--model", "-m", type=str, default=None, help="Override Ollama model")
@click.option("--instant", is_flag=True, default=False, help="Instant 0.05s synthesis with guaranteed playable engine archetype")
@click.option("--no-open", is_flag=True, default=False, help="Do not automatically open game in browser")
@click.option("--no-web-learn", is_flag=True, default=False, help="Skip online game research and use curated offline briefs only")
@click.option("--temperature", "-t", type=float, default=None, help="Sampling temperature")
def generate_cmd(
    prompt: str,
    category: Optional[str],
    model: Optional[str],
    instant: bool,
    no_open: bool,
    no_web_learn: bool,
    temperature: Optional[float],
) -> None:
    """Generate a brand new HTML5 game from a prompt."""
    print_banner()

    settings = get_settings(
        model=model,
        auto_open=not no_open,
        learn_from_web=False if no_web_learn else None,
        temperature=temperature,
    )
    agent = Agent(settings)

    async def _run():
        print_status(f"Requesting game: [bold yellow]\"{prompt}\"[/bold yellow]")
        if category:
            print_status(f"Category: [cyan]{category}[/cyan]")
        if instant:
            print_status("[bold green]Mode: Instant Guaranteed Archetype[/bold green]")
        else:
            print_status(f"Model: [magenta]{settings.active_model_display}[/magenta]")

        # Stream container
        stream_buffer = []

        def on_stream(delta: str):
            stream_buffer.append(delta)

        with console.status("[bold green]Synthesizing game code...", spinner="dots"):
            try:
                game = await agent.create_game(
                    prompt=prompt,
                    category=category,
                    stream_callback=on_stream if settings.stream_output else None,
                    auto_open=not no_open,
                    instant=instant,
                )
            except Exception as e:
                print_error(f"Generation failed: {e}")
                return

        print_game_card(game)
        if not no_open:
            console.print("[bold green]🚀 Game opened in your default browser![/bold green]")
        else:
            console.print(f"[dim]Game saved at: {game.file_path}[/dim]")

    asyncio.run(_run())
