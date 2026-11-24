"""Authentication, rate limiting, and security headers for the 8Gen server.

These helpers protect public deployments:

* Optional token authentication (``EIGHTGEN_API_TOKEN``) guarding the dashboard
  and every endpoint that can spend LLM quota or mutate stored games.
* A per-client sliding-window rate limit on mutating requests.
* Baseline security headers and a Content-Security-Policy for our own pages
  (generated game documents opt into an isolated ``sandbox`` CSP instead).
"""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
from typing import Dict, List, Optional
from urllib.parse import quote

from fastapi.responses import JSONResponse, RedirectResponse

SESSION_COOKIE = "eightgen_session"
SESSION_TTL_SECONDS = 12 * 60 * 60  # 12 hours

# Paths reachable without a session even when authentication is enabled.
PUBLIC_PATHS = frozenset({"/login", "/api/health", "/api/auth/login", "/api/auth/logout"})
PUBLIC_PATH_PREFIXES = ("/static/", "/favicon.ico", "/openapi.json")

# HTML pages we render ourselves (games set their own sandbox CSP instead).
CSP_EXEMPT_PREFIXES = ("/docs", "/redoc", "/api/games")

APP_CSP = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "frame-src 'self'; "
    "form-action 'self'"
)

# CSP applied to generated game HTML: scripts may run, but the document is in an
# opaque origin (no access to cookies, storage, or the parent page).
GAME_SANDBOX_CSP = "sandbox allow-scripts allow-pointer-lock"


def sign_session_token(api_token: str, now: Optional[float] = None) -> str:
    """Create an expiring, HMAC-signed session value derived from the API token."""
    expires = int((now or time.time()) + SESSION_TTL_SECONDS)
    signature = hmac.new(
        api_token.encode("utf-8"), str(expires).encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{expires}.{signature}"


def verify_session_token(api_token: str, value: Optional[str]) -> bool:
    """Validate a session value produced by :func:`sign_session_token`."""
    if not value or "." not in value:
        return False
    expires_str, _, signature = value.partition(".")
    expected = hmac.new(
        api_token.encode("utf-8"), expires_str.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False
    try:
        expires = int(expires_str)
    except ValueError:
        return False
    return time.time() < expires


def session_cookie_valid(api_token: str, cookie_header: Optional[str]) -> bool:
    """Check the raw ``Cookie`` header for a valid session cookie."""
    if not api_token or not cookie_header:
        return False
    for chunk in cookie_header.split(";"):
        name, _, value = chunk.strip().partition("=")
        if name == SESSION_COOKIE:
            return verify_session_token(api_token, value)
    return False


def is_public_path(path: str) -> bool:
    """Return True when a path does not require a session."""
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PATH_PREFIXES)


def client_ip(headers, client) -> str:
    """Best-effort client IP, honoring ``X-Forwarded-For`` from our proxies."""
    forwarded = headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if client is not None:
        return getattr(client, "host", None) or (client[0] if client else "unknown")
    return "unknown"


class RateLimiter:
    """In-memory sliding-window limiter keyed by an arbitrary string."""

    def __init__(self, limit_per_minute: int, window_seconds: float = 60.0):
        self.limit = limit_per_minute
        self.window = window_seconds
        self._hits: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record a hit for ``key``; False when the limit is exhausted."""
        if self.limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            cutoff = now - self.window
            hits = self._hits.setdefault(key, [])
            hits[:] = [t for t in hits if t > cutoff]
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            if len(self._hits) > 4096:
                for stale_key in [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]:
                    del self._hits[stale_key]
            return True


def install_security(app, settings) -> RateLimiter:
    """Attach the security middleware to ``app`` and return its rate limiter.

    The limiter is exposed as ``app.state.limiter`` so the WebSocket route can
    reuse the same budget (HTTP middleware does not run for WS handshakes).
    """
    from fastapi import Request

    limiter = RateLimiter(settings.rate_limit)
    app.state.limiter = limiter

    auth_enabled = bool(settings.api_token)
    app.state.auth_enabled = auth_enabled
    api_token = settings.api_token or ""

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        path = request.url.path
        method = request.method

        # 1. Rate limit mutating traffic (generation, refinement, deletion...).
        if method not in ("GET", "HEAD", "OPTIONS") and path.startswith(("/api/", "/ws/")):
            ip = client_ip(request.headers, request.client)
            if not limiter.allow(f"{method}:{path}:{ip}"):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests, please slow down."},
                )

        # 2. Optional token authentication.
        if auth_enabled and not is_public_path(path):
            if not session_cookie_valid(api_token, request.headers.get("cookie")):
                if path.startswith(("/api/", "/ws/")):
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Authentication required."},
                    )
                next_target = path
                if request.url.query:
                    next_target += f"?{request.url.query}"
                if not next_target.startswith("/") or next_target.startswith("//"):
                    next_target = "/"
                return RedirectResponse(
                    url=f"/login?next={quote(next_target)}", status_code=302
                )

        response = await call_next(request)

        # 3. Baseline security headers.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        if (
            "content-security-policy" not in response.headers
            and not path.startswith(CSP_EXEMPT_PREFIXES)
            and "text/html" in response.headers.get("content-type", "")
        ):
            response.headers["Content-Security-Policy"] = APP_CSP
        return response

    return limiter
