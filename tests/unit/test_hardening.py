"""Unit tests for SVG sanitization, open-redirect guards, and repository helpers."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from eightgen.llm.image_gen import ImageGenerationError, _sanitize_svg
from eightgen.server.app import _safe_next, create_app
from eightgen.storage.models import Game, GameVersion


def test_sanitize_svg_strips_active_content():
    dirty = (
        '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)">'
        "<script>alert(2)</script>"
        "<foreignObject><body>bad</body></foreignObject>"
        '<a href="javascript:alert(3)"><rect width="10" height="10" style="background:url(javascript:alert(4))"/></a>'
        '<circle cx="5" cy="5" r="4" fill="#0ff"/>'
        "</svg>"
    )
    clean = _sanitize_svg(dirty)
    low = clean.lower()
    assert "<script" not in low
    assert "onload" not in low
    assert "foreignobject" not in low
    assert "javascript:" not in low
    assert "<circle" in low


def test_sanitize_svg_rejects_empty():
    with pytest.raises(ImageGenerationError):
        _sanitize_svg("<script>alert(1)</script>")


def test_safe_next_rejects_open_redirects():
    assert _safe_next("/games/abc?v=1") == "/games/abc?v=1"
    assert _safe_next("https://evil.com/phish") == "/"
    assert _safe_next("//evil.com/phish") == "/"
    assert _safe_next("/\\evil.com") == "/"
    assert _safe_next("/ok\r\nSet-Cookie: a=b") == "/"
    assert _safe_next("") == "/"


def test_asset_static_files_sets_svg_csp(monkeypatch, tmp_path):
    games_dir = tmp_path / "games"
    assets_dir = games_dir / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "sprite.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>',
        encoding="utf-8",
    )
    monkeypatch.setenv("EIGHTGEN_OUTPUT_DIR", str(games_dir))
    monkeypatch.setenv("EIGHTGEN_DB_PATH", str(games_dir / "8gen.db"))

    client = TestClient(create_app())
    res = client.get("/static/assets/sprite.svg")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert "sandbox" in (res.headers.get("Content-Security-Policy") or "")


def test_repository_summaries_and_add_version(repo, tmp_settings):
    game_path = tmp_settings.output_dir / "test_game.html"
    g = Game(
        id="abc12345",
        title="Test Game",
        slug="test-game",
        description="A test",
        category="arcade",
        tags=["arcade", "neon"],
        file_path=game_path,
        current_version=1,
        versions=[
            GameVersion(
                version=1,
                prompt="base",
                html_content="<html><body>v1</body></html>",
                model="mock",
            )
        ],
    )
    repo.save(g)

    summaries = repo.list_summaries()
    assert len(summaries) == 1
    assert summaries[0]["id"] == "abc12345"
    assert "versions" not in summaries[0]
    assert summaries[0]["version_count"] == 1

    updated = repo.add_version(
        "abc12345",
        GameVersion(
            version=2,
            prompt="add juice",
            html_content="<html><body>v2</body></html>",
            model="mock",
            change_summary="add juice",
        ),
    )
    assert updated is not None
    assert updated.current_version == 2
    assert len(updated.versions) == 2
    assert game_path.read_text(encoding="utf-8") == "<html><body>v2</body></html>"
