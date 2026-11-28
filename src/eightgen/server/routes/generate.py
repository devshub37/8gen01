"""Generation API routes."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

from eightgen.config.loader import get_settings
from eightgen.core.agent import Agent
from eightgen.core.engine.references import REFERENCE_GAME_MAP
from eightgen.utils.logger import get_logger

logger = get_logger("eightgen.server.generate")

router = APIRouter(prefix="/api/generate", tags=["generate"])


def get_agent(request: Request) -> Agent:
    try:
        settings = getattr(request.app.state, "settings", None) or get_settings()
        return Agent(settings)
    except ValueError:
        logger.exception("Could not initialize the game agent")
        raise HTTPException(
            status_code=500,
            detail="The game engine is not configured correctly. Check the server logs.",
        )


class GenerateRequest(BaseModel):
    prompt: str = Field(default="", max_length=4000)
    category: Optional[str] = Field(default=None, max_length=64)
    model: Optional[str] = Field(default=None, max_length=128)
    instant: bool = False
    game_reference: Optional[str] = Field(default=None, max_length=64)


@router.post("")
async def generate_game(payload: GenerateRequest, agent: Agent = Depends(get_agent)):
    """Generate a new game via REST API."""
    reference = (payload.game_reference or "").strip().lower() or None
    if not payload.prompt.strip() and not reference:
        raise HTTPException(status_code=400, detail="Either prompt or game_reference is required.")
    if reference and reference not in REFERENCE_GAME_MAP:
        raise HTTPException(status_code=400, detail="Unknown game reference.")
    try:
        if payload.model:
            agent.provider.model = payload.model
        game = await agent.create_game(
            prompt=payload.prompt,
            category=payload.category,
            auto_open=False,
            instant=payload.instant,
            game_reference=reference,
        )
        return game.model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Game generation failed")
        raise HTTPException(
            status_code=500,
            detail="Game generation failed. Check the server logs for details.",
        )
