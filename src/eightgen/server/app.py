"""FastAPI application factory and routes."""

import asyncio
import hmac
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from eightgen.config.loader import get_settings
from eightgen.config.settings import Settings, is_vercel
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
from eightgen.utils.logger import get_logger

logger = get_logger("eightgen.server")

SERVER_DIR = Path(__file__).parent
STATIC_DIR = SERVER_DIR / "static"
TEMPLATES_DIR = SERVER_DIR / "templates"


class LoginRequest(BaseModel):
    token: str


def _safe_next(next_target: str) -> str:
    """Only allow redirecting back to a local path.

    Rejects absolute URLs, protocol-relative URLs, backslashes, and control
    characters, which are the common open-redirect bypasses.
    """
    if not next_target:
        return "/"
    if any(ch in next_target for ch in ("\r", "\n", "\t", "\\")):
        return "/"
    parsed = urlparse(next_target)
    if parsed.scheme or parsed.netloc:
        return "/"
    if not parsed.path.startswith("/") or parsed.path.startswith("//"):
        return "/"
    return parsed.path + (f"?{parsed.query}" if parsed.query else "")


class AssetStaticFiles(StaticFiles):
    """Static files with a locked-down policy for user/LLM-generated SVGs."""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        if path.lower().endswith(".svg"):
            # LLM-generated SVG is untrusted. Even if a file contains a
            # <script> or on* handler, the sandbox CSP prevents execution when
            # the asset is opened directly.
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; style-src 'unsafe-inline'; sandbox"
            )
        return response


def _request_settings(request: Request) -> Settings:
    """Return the app's injected settings, falling back to the global loader."""
    return getattr(request.app.state, "settings", None) or get_settings()


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """Instantiate and configure FastAPI application."""
    settings = settings or get_settings()

    app = FastAPI(
        title="8Gen Arcade Server",
        description="Local AI Game Generator Web Dashboard",
        version="0.1.0",
    )
    app.state.settings = settings

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
    app.mount("/static/assets", AssetStaticFiles(directory=str(assets_dir)), name="assets")
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
        current_settings = _request_settings(request)
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
    async def health_check(request: Request):
        current_settings = _request_settings(request)
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
        current_settings = _request_settings(request)
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
        current_settings = _request_settings(request)
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
        current_settings = _request_settings(request)
        try:
            agent = Agent(current_settings)
        except ValueError:
            logger.exception("Could not initialize the game agent")
            return HTMLResponse("Configuration error. Check the server logs.", status_code=500)
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

    # API-key editing intentionally lives in the CLI (`8gen config set-key`).
    # A browser endpoint that rewrites .env is unnecessary attack surface and
    # was removed in favour of environment variables / CLI configuration.

    return app


app = create_app()
