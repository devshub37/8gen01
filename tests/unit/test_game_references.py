"""Unit tests for Game Reference selector, simple reference synthesis, and sticky page sections."""

import pytest
from starlette.testclient import TestClient

from eightgen.config.settings import Settings
from eightgen.core.engine.references import REFERENCE_GAMES
from eightgen.core.generator import GameGenerator
from eightgen.core.validator import GameValidator
from eightgen.llm.base import LLMMessage, LLMProvider, LLMResponse
from eightgen.llm.prompt_builder import PromptBuilder
from eightgen.server.app import create_app


class FailingConfigProvider(LLMProvider):
    """Simulates missing API configuration triggering ValueError fallback."""

    def __init__(self):
        self.model = "mock-gemini"

    async def generate(self, messages: list[LLMMessage], temperature: float = 0.7) -> LLMResponse:
        raise ValueError("Missing API key")

    async def stream(self, messages: list[LLMMessage], temperature: float = 0.7):
        raise ValueError("Missing API key")
        yield ""  # pragma: no cover

    async def is_healthy(self) -> bool:
        return False

    async def list_models(self) -> list[str]:
        return []


def test_dashboard_replaces_category_with_game_reference_and_uses_page_sections(monkeypatch, tmp_path):
    monkeypatch.setenv("EIGHTGEN_OUTPUT_DIR", str(tmp_path / "games"))
    monkeypatch.setenv("EIGHTGEN_DB_PATH", str(tmp_path / "8gen.db"))

    app = create_app()
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    html = res.text

    # Category tabs removed from Studio Console
    assert 'class="category-tab' not in html
    assert ">Category</label>" not in html

    # Game Reference dropdown present with all reference options
    assert 'id="game-reference-select"' in html
    for spec in REFERENCE_GAMES:
        assert f'value="{spec.id}"' in html
        assert spec.label in html

    # Sticky main page sections match top nav links
    assert html.count('class="page-section') == 4
    for section_id in ("workbench", "archetypes", "assets", "library"):
        assert f'id="{section_id}" class="page-section' in html


def test_generate_route_accepts_game_reference_with_blank_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv("EIGHTGEN_OUTPUT_DIR", str(tmp_path / "games"))
    monkeypatch.setenv("EIGHTGEN_DB_PATH", str(tmp_path / "8gen.db"))

    app = create_app()
    client = TestClient(app)

    # Empty both prompt & reference -> 400
    bad_res = client.post("/api/generate", json={"prompt": ""})
    assert bad_res.status_code == 400

    # Valid game_reference with empty prompt + instant=True -> generates runnable simple reference game
    res = client.post(
        "/api/generate",
        json={"prompt": "", "game_reference": "tic-tac-toe", "instant": True},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["category"] == "puzzle"
    assert "tic-tac-toe" in data["tags"]
    html = data["versions"][-1]["html_content"]
    assert "Tic-Tac-Toe" in html
    assert GameValidator.validate(html).is_valid


@pytest.mark.asyncio
async def test_generator_falls_back_to_simple_reference_game_on_config_error(tmp_path):
    settings = Settings(
        output_dir=tmp_path / "games",
        db_path=tmp_path / "8gen.db",
    )
    generator = GameGenerator(FailingConfigProvider(), PromptBuilder(), settings)
    html = await generator.generate(
        prompt="Simple dino jump game",
        game_reference="dino-runner",
        instant=False,
    )
    assert "Simple Dino Runner" in html
    assert GameValidator.validate(html).is_valid
