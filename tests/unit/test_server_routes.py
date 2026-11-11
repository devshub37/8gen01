"""Unit tests for FastAPI dashboard and REST endpoints."""

from starlette.testclient import TestClient
from eightgen.server.app import create_app


def test_dashboard_and_archetype_routes():
    app = create_app()
    client = TestClient(app)

    # 1. Dashboard View
    res = client.get("/")
    assert res.status_code == 200
    assert "8Gen Studio" in res.text
    assert "Universal SaaS Design" in res.text
    assert "Studio Workbench" in res.text
    assert 'id="nav-indicator"' in res.text
    assert 'data-section="workbench"' in res.text
    assert 'data-section="assets"' in res.text
    assert 'data-section="library"' in res.text
    assert 'data-ws-enabled="true"' in res.text

    # Health check
    health_res = client.get("/api/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "ok"

    # 2. Archetype route
    res = client.get("/api/games/archetype/shooter")
    assert res.status_code == 200
    assert "Neon Space Defender" in res.text

    res = client.get("/api/games/archetype/snake")
    assert res.status_code == 200
    assert "Cyber Snake" in res.text

    res = client.get("/api/games/archetype/brick")
    assert res.status_code == 200
    assert "Quantum Breakout" in res.text

    res = client.get("/api/games/archetype/drone")
    assert res.status_code == 200
    assert "Aero Drone Odyssey" in res.text

    # 3. List games API
    res = client.get("/api/games")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # 4. Instant Generate API
    res = client.post(
        "/api/generate",
        json={"prompt": "Retro Space Invaders", "category": "shooter", "instant": True},
    )
    assert res.status_code == 200
    data = res.json()
    assert "id" in data
    assert "title" in data
    game_id = data["id"]

    # 5. Play game endpoint
    play_res = client.get(f"/api/games/{game_id}/play")
    assert play_res.status_code == 200
    assert "<!DOCTYPE html>" in play_res.text

    # 6. Download game endpoint
    dl_res = client.get(f"/api/games/{game_id}/download")
    assert dl_res.status_code == 200
    assert "<!DOCTYPE html>" in dl_res.text


def test_vercel_mode_routes_and_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("EIGHTGEN_OUTPUT_DIR", str(tmp_path / "games"))
    monkeypatch.setenv("EIGHTGEN_DB_PATH", str(tmp_path / "games" / "8gen.db"))

    app = create_app()
    client = TestClient(app)

    res = client.get("/")
    assert res.status_code == 200
    assert 'data-ws-enabled="false"' in res.text

    health = client.get("/api/health").json()
    assert health["vercel"] is True

    key_res = client.post("/api/settings/key", json={"api_key": "test", "provider": "gemini"})
    assert key_res.status_code == 400

    # Generate, remove disk HTML, verify download falls back cleanly to SQLite HTML
    gen_res = client.post(
        "/api/generate",
        json={"prompt": "Cyber Snake", "category": "arcade", "instant": True},
    )
    assert gen_res.status_code == 200
    game = gen_res.json()
    for p in (tmp_path / "games").glob("*.html"):
        p.unlink()

    dl_res = client.get(f"/api/games/{game['id']}/download")
    assert dl_res.status_code == 200
    assert "<!DOCTYPE html>" in dl_res.text


def test_image_generation_svg_fallback_and_listing(monkeypatch, tmp_path):
    monkeypatch.setenv("EIGHTGEN_OUTPUT_DIR", str(tmp_path / "games"))
    monkeypatch.setenv("EIGHTGEN_DB_PATH", str(tmp_path / "games" / "8gen.db"))
    monkeypatch.setenv("GEMINI_API_KEY", "test-fake-key")

    from eightgen.llm.base import LLMResponse
    from eightgen.llm.gemini import GeminiProvider
    from eightgen.llm.image_gen import ImageGenerator

    async def fake_native_fail(self, prompt):
        raise RuntimeError("gemini-2.5-flash-image HTTP 429")

    async def fake_gemini_generate(self, messages, temperature=0.7, **kwargs):
        return LLMResponse(
            content='```svg\n<svg viewBox="0 0 512 512"><rect width="512" height="512" fill="#000"/><circle cx="256" cy="256" r="80" fill="#0ff"/></svg>\n```',
            model="gemini-3-flash-preview",
        )

    monkeypatch.setattr(ImageGenerator, "_generate_via_google_native_image", fake_native_fail)
    monkeypatch.setattr(GeminiProvider, "generate", fake_gemini_generate)

    app = create_app()
    client = TestClient(app)

    img_res = client.post(
        "/api/images/generate",
        json={"prompt": "neon laser orb", "style": "pixel-art"},
    )
    assert img_res.status_code == 200
    payload = img_res.json()
    assert payload["format"] == "svg"
    assert payload["mime_type"] == "image/svg+xml"
    assert payload["data_url"].startswith("data:image/svg+xml;base64,")
    assert payload["filename"].endswith(".svg")

    list_res = client.get("/api/images")
    assert list_res.status_code == 200
    items = list_res.json()
    assert any(item["filename"] == payload["filename"] for item in items)


