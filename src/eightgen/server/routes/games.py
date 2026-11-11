"""Games REST API routes."""

from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Response
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from eightgen.config.loader import get_settings
from eightgen.core.agent import Agent
from eightgen.core.engine.archetypes import (
    build_space_shooter_game,
    build_brick_breaker_game,
    build_cyber_snake_game,
    build_flappy_drone_game,
)
from eightgen.storage.models import Game

router = APIRouter(prefix="/api/games", tags=["games"])


def get_agent() -> Agent:
    return Agent(get_settings())


@router.get("/archetype/{name}", response_class=HTMLResponse)
def get_archetype_html(name: str):
    """Serve a guaranteed playable arcade archetype instantly."""
    n = name.lower()
    if "shooter" in n or "space" in n:
        return HTMLResponse(content=build_space_shooter_game("Neon Space Defender"))
    elif "snake" in n:
        return HTMLResponse(content=build_cyber_snake_game("Cyber Snake 2099"))
    elif "brick" in n or "breaker" in n:
        return HTMLResponse(content=build_brick_breaker_game("Quantum Breakout"))
    elif "drone" in n or "flappy" in n:
        return HTMLResponse(content=build_flappy_drone_game("Aero Drone Odyssey"))
    return HTMLResponse(content=build_space_shooter_game("Neon Space Defender"))


class RefineRequest(BaseModel):
    instruction: str


@router.get("", response_model=List[dict])
def list_games(tag: Optional[str] = None, agent: Agent = Depends(get_agent)):
    """List all games."""
    games = agent.list_games(tag=tag)
    return [g.model_dump(mode="json") for g in games]


@router.get("/{game_id}")
def get_game(game_id: str, agent: Agent = Depends(get_agent)):
    """Get single game metadata."""
    game = agent.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game.model_dump(mode="json")


@router.get("/{game_id}/play", response_class=HTMLResponse)
def play_game(game_id: str, version: Optional[int] = None, agent: Agent = Depends(get_agent)):
    """Serve the raw game HTML for in-browser or iframe playing."""
    game = agent.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if version is not None:
        for v in game.versions:
            if v.version == version:
                return HTMLResponse(content=v.html_content)

    return HTMLResponse(content=game.latest_html)


@router.get("/{game_id}/download")
def download_game(game_id: str, agent: Agent = Depends(get_agent)):
    """Download game as HTML file."""
    game = agent.get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.file_path.is_file():
        return FileResponse(
            path=game.file_path,
            filename=game.file_path.name,
            media_type="text/html",
        )
    return Response(
        content=game.latest_html,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{game.file_path.name}"'},
    )


@router.post("/{game_id}/refine")
async def refine_game(game_id: str, payload: RefineRequest, agent: Agent = Depends(get_agent)):
    """Refine an existing game."""
    try:
        updated = await agent.refine_game(
            game_id=game_id,
            instruction=payload.instruction,
            auto_open=False,
        )
        return updated.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{game_id}")
def delete_game(game_id: str, agent: Agent = Depends(get_agent)):
    """Delete a game."""
    success = agent.delete_game(game_id)
    if not success:
        raise HTTPException(status_code=404, detail="Game not found or could not be deleted")
    return {"status": "deleted", "id": game_id}
