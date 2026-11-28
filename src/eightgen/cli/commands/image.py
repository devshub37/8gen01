"""CLI image generation command."""

import asyncio
import click
from eightgen.cli.display import console, print_banner, print_status, print_error, print_success
from eightgen.config.loader import get_settings
from eightgen.llm.image_gen import ImageGenerator
from eightgen.utils.browser import open_in_browser


@click.command(name="image")
@click.argument("prompt", type=str)
@click.option("--style", "-s", type=click.Choice(["pixel-art", "retro-arcade", "scifi-background", "default"]), default="pixel-art", help="Art style")
@click.option("--size", type=str, default="1024x1024", help="Image dimension")
@click.option("--no-open", is_flag=True, default=False, help="Do not open image in preview")
def image_cmd(prompt: str, style: str, size: str, no_open: bool) -> None:
    """Generate game assets, pixel sprites, or backgrounds using Gemini Image Gen."""
    print_banner()
    settings = get_settings()
    gen = ImageGenerator(settings)

    async def _run():
        print_status(f"Generating game art for: [bold yellow]\"{prompt}\"[/bold yellow]")
        print_status(f"Style: [cyan]{style}[/cyan] | Size: [cyan]{size}[/cyan]")

        with console.status("[bold green]Synthesizing image with Gemini Image Model...", spinner="dots"):
            try:
                result = await gen.generate_image(prompt=prompt, style=style, size=size)
            except Exception as e:
                print_error(f"Image generation failed: {e}")
                return

        print_success(f"Image saved: [bold cyan]{result['filepath']}[/bold cyan]")
        console.print(f"[dim]Data URL ready: {result['data_url'][:60]}...[/dim]")

        if not no_open:
            open_in_browser(result["filepath"])

    asyncio.run(_run())
