"""CLI serve command."""

from typing import Optional
import click
import uvicorn
from eightgen.cli.display import print_banner, print_status
from eightgen.config.loader import get_settings
from eightgen.utils.browser import open_in_browser


@click.command(name="serve")
@click.option("--host", "-h", type=str, default=None, help="Host address to bind")
@click.option("--port", "-p", type=int, default=None, help="Port to listen on")
@click.option("--no-open", is_flag=True, default=False, help="Do not open web dashboard automatically")
def serve_cmd(host: Optional[str], port: Optional[int], no_open: bool) -> None:
    """Launch the 8Gen web dashboard and arcade gallery."""
    print_banner()
    settings = get_settings(server_host=host, server_port=port)
    url = f"http://{settings.server_host}:{settings.server_port}"
    print_status(f"Starting 8Gen Web Dashboard at [bold cyan]{url}[/bold cyan]")

    if not no_open:
        # Open in background after short delay
        import threading
        import time

        def _opener():
            time.sleep(0.8)
            open_in_browser(url)

        threading.Thread(target=_opener, daemon=True).start()

    uvicorn.run(
        "eightgen.server.app:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
        log_level="info",
    )
