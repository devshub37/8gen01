"""Base plugin interface."""

from abc import ABC
from typing import List, Optional


class Plugin(ABC):
    """Base class for 8Gen plugins."""
    name: str = "base_plugin"
    version: str = "0.1.0"
    description: str = ""

    async def pre_generate(self, prompt: str, category: Optional[str]) -> None:
        """Called immediately before LLM generation begins."""
        pass

    async def post_generate(self, prompt: str, html: str) -> None:
        """Called immediately after successful game generation."""
        pass

    async def pre_refine(self, game_id: str, instruction: str) -> None:
        """Called before refining a game."""
        pass

    async def post_refine(self, game_id: str, html: str) -> None:
        """Called after refining a game."""
        pass

    async def on_validate_error(self, html: str, errors: List[str]) -> None:
        """Called when generated HTML fails validation."""
        pass
