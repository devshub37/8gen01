"""Unit tests for server security helpers: sessions, rate limiting, paths."""

import time

from eightgen.server.security import (
    RateLimiter,
    client_ip,
    is_public_path,
    session_cookie_valid,
    sign_session_token,
    verify_session_token,
)

TOKEN = "secret-token"


def test_session_token_roundtrip():
    value = sign_session_token(TOKEN)
    assert verify_session_token(TOKEN, value)
    assert session_cookie_valid(TOKEN, f"other=1; eightgen_session={value}; x=2")


def test_session_token_wrong_token_rejected():
    value = sign_session_token(TOKEN)
    assert not verify_session_token("different-token", value)
    assert not session_cookie_valid("different-token", f"eightgen_session={value}")


def test_session_token_expired_rejected():
    past = time.time() - 1
    value = sign_session_token(TOKEN, now=past - 12 * 60 * 60)  # expired 12h+ ago
    assert not verify_session_token(TOKEN, value)


def test_session_token_garbage_rejected():
    assert not verify_session_token(TOKEN, None)
    assert not verify_session_token(TOKEN, "")
    assert not verify_session_token(TOKEN, "not-a-token")
    assert not verify_session_token(TOKEN, "abc.def")


def test_public_paths():
    assert is_public_path("/login")
    assert is_public_path("/api/health")
    assert is_public_path("/static/css/x.css")
    assert not is_public_path("/")
    assert not is_public_path("/api/games")
    assert not is_public_path("/ws/generate")


def test_rate_limiter_allows_then_blocks():
    limiter = RateLimiter(limit_per_minute=2, window_seconds=60.0)
    assert limiter.allow("k")
    assert limiter.allow("k")
    assert not limiter.allow("k")
    assert limiter.allow("other-key")  # per-key budget


def test_rate_limiter_disabled_when_zero():
    limiter = RateLimiter(limit_per_minute=0)
    for _ in range(100):
        assert limiter.allow("k")


def test_rate_limiter_window_expires():
    limiter = RateLimiter(limit_per_minute=1, window_seconds=0.05)
    assert limiter.allow("k")
    assert not limiter.allow("k")
    time.sleep(0.06)
    assert limiter.allow("k")


def test_client_ip_prefers_forwarded_header():
    class Headers(dict):
        pass

    class Client:
        host = "10.0.0.1"

    assert client_ip(Headers({"x-forwarded-for": "1.2.3.4, 5.6.7.8"}), Client()) == "1.2.3.4"
    assert client_ip(Headers({}), Client()) == "10.0.0.1"
