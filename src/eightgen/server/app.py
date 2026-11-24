"""FastAPI application factory and routes."""

import asyncio
import hmac
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from eightgen.config.loader import get_settings
from eightgen.config.settings import is_vercel
from eightgen.core.agent import Agent
from eightgen.core.engine.references import REFERENCE_GAMES
from eightgen.server.routes.games import router as games_router
from eightgen.server.routes.generate import router as generate_router
from eightgen.server.routes.ws import router as ws_router
from eightgen.server.routes.images import router as images_router
from eightgen.server.security import (
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    install_security,
    session_cookie_valid,
    sign_session_token,
)

SERVER_DIR = Path(__file__).parent
STATIC_DIR = SERVER_DIR / "static"
TEMPLATES_DIR = SERVER_DIR / "templates"


class KeyUpdateRequest(BaseModel):
    api_key: str
    provider: str = "gemini"


class LoginRequest(BaseModel):
    token: str


def _safe_next(next_target: str) -> str:
    """Only allow redirecting back to a local path."""
    if next_target.startswith("/") and not next_target.startswith("//"):
        return next_target
    return "/"


def create_app() -> FastAPI:
    """Instantiate and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="8Gen Arcade Server",
        description="Local AI Game Generator Web Dashboard",
        version="0.1.0",
    )

    # CORS: disabled unless origins are explicitly configured. The dashboard is
    # same-origin, so a public deployment must not accept arbitrary origins.
    cors_origins = [o.strip() for o in (settings.cors_origins or "").split(",") if o.strip()]
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization"],
        )

    # Optional token auth, rate limiting, and security headers.
    install_security(app, settings)

    # Mount generated game assets BEFORE the generic /static mount: Starlette
    # matches mounts in registration order, so /static/assets/... must come first.
    assets_dir = settings.output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Templates
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    # Include API Routers
    app.include_router(games_router)
    app.include_router(generate_router)
    app.include_router(ws_router)
    app.include_router(images_router)

    @app.get("/", response_class=HTMLResponse)
    async def dashboard_view(request: Request):
        current_settings = get_settings()
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "model_name": current_settings.active_model_display,
                "provider": current_settings.resolved_provider,
                "has_key": bool(current_settings.gemini_api_key),
                "is_vercel": is_vercel(),
                "references": REFERENCE_GAMES,
            },
        )

    @app.get("/api/health")
    async def health_check():
        current_settings = get_settings()
        resolved = current_settings.resolved_provider
        return {
            "status": "ok",
            "provider": resolved,
            "model": current_settings.gemini_model if resolved == "gemini" else current_settings.model,
            "has_key": bool(current_settings.gemini_api_key),
            "vercel": is_vercel(),
            "auth_enabled": bool(current_settings.api_token),
        }

    @app.get("/login", response_class=HTMLResponse)
    async def login_view(request: Request, next: str = "/"):
        current_settings = get_settings()
        if not current_settings.api_token:
            return RedirectResponse(url="/", status_code=302)
        if session_cookie_valid(current_settings.api_token, request.headers.get("cookie")):
            return RedirectResponse(url=_safe_next(next), status_code=302)
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"next": _safe_next(next)},
        )

    @app.post("/api/auth/login")
    async def login(payload: LoginRequest, request: Request):
        """Exchange the deployment access token for a signed session cookie."""
        current_settings = get_settings()
        if not current_settings.api_token:
            raise HTTPException(
                status_code=400,
                detail="Authentication is disabled on this deployment (EIGHTGEN_API_TOKEN is not set).",
            )
        if not hmac.compare_digest(
            payload.token.encode("utf-8"), current_settings.api_token.encode("utf-8")
        ):
            await asyncio.sleep(0.5)  # slow down brute-force attempts
            raise HTTPException(status_code=401, detail="Invalid access token.")

        response = JSONResponse({"status": "ok"})
        response.set_cookie(
            key=SESSION_COOKIE,
            value=sign_session_token(current_settings.api_token),
            max_age=SESSION_TTL_SECONDS,
            httponly=True,
            samesite="strict",
            secure=request.url.scheme == "https",
            path="/",
        )
        return response

    @app.post("/api/auth/logout")
    async def logout():
        response = JSONResponse({"status": "ok"})
        response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    @app.get("/games/{game_id}", response_class=HTMLResponse)
    async def game_view(request: Request, game_id: str):
        current_settings = get_settings()
        try:
            agent = Agent(current_settings)
        except ValueError as exc:
            return HTMLResponse(f"Configuration error: {exc}", status_code=500)
        game = agent.get_game(game_id)
        if not game:
            return HTMLResponse("Game not found", status_code=404)
        return templates.TemplateResponse(
            request=request,
            name="game.html",
            context={
                "game": game,
                "model_name": current_settings.active_model_display,
            },
        )

    @app.post("/api/settings/key")
    async def save_api_key(payload: KeyUpdateRequest):
        """Save Gemini API Key to local .env and runtime environment."""
        if is_vercel():
            raise HTTPException(
                status_code=400,
                detail="On Vercel deployments, configure GEMINI_API_KEY in Vercel Project Environment Variables.",
            )

        import os
        from dotenv import load_dotenv

        env_file = Path("./.env")
        lines = []
        if env_file.exists():
            lines = env_file.read_text().splitlines()

        new_lines = []
        has_key = False
        has_provider = False
        for line in lines:
            if line.startswith("GEMINI_API_KEY=") or line.startswith("EIGHTGEN_GEMINI_API_KEY="):
                new_lines.append(f"GEMINI_API_KEY={payload.api_key.strip()}")
                has_key = True
            elif line.startswith("EIGHTGEN_PROVIDER=") or line.startswith("PROVIDER="):
                new_lines.append(f"EIGHTGEN_PROVIDER={payload.provider.strip()}")
                has_provider = True
            else:
                new_lines.append(line)

        if not has_key:
            new_lines.append(f"GEMINI_API_KEY={payload.api_key.strip()}")
        if not has_provider:
            new_lines.append(f"EIGHTGEN_PROVIDER={payload.provider.strip()}")

        env_file.write_text("\n".join(new_lines) + "\n")

        # Update current process environment immediately
        os.environ["GEMINI_API_KEY"] = payload.api_key.strip()
        os.environ["EIGHTGEN_PROVIDER"] = payload.provider.strip()
        load_dotenv(override=True)

        return {"status": "ok", "provider": payload.provider}

    return app


app = create_app()
