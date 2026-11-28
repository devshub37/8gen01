"""Unit tests for curated design knowledge and online game-research learner."""

from __future__ import annotations

import json
import pytest

from eightgen.config.settings import Settings
from eightgen.core.engine.design_knowledge import (
    DESIGN_SPECS,
    detect_design_spec,
    render_design_brief,
)
from eightgen.core.engine.web_learner import (
    LearnedGameKnowledge,
    _classify_sentences,
    _is_allowed_url,
    learn_from_similar_games,
)
from eightgen.core.generator import GameGenerator
from eightgen.llm.prompt_builder import PromptBuilder
from tests.conftest import MockLLMProvider


def test_detect_design_spec_genres_and_word_boundaries():
    assert detect_design_spec("Make a celeste style platformer with double jump").id == "platformer"
    assert detect_design_spec("Create a twin-stick arena shooter like vampire survivors").id == "twin-stick"
    assert detect_design_spec("Build asteroids with ship thrust and screen wrap").id == "asteroids"
    assert detect_design_spec("Tetris falling blocks with wall kicks").id == "tetris"
    assert detect_design_spec("Classic pong paddle duel", game_reference="pong").id == "pong"
    assert detect_design_spec("Slingshot angry birds physics catapult").id == "physics-slingshot"
    assert detect_design_spec("4-lane rhythm beat game with BPM").id == "rhythm"
    # Whole-word matching: 'card' must NOT falsely trigger 'car' (racing)
    assert detect_design_spec("Make a memory card matching game").id == "puzzle"


def test_render_design_brief_contains_controls_and_physics():
    for spec in DESIGN_SPECS:
        brief = render_design_brief(spec)
        assert "CONTROLS" in brief
        assert "PHYSICS / TIMING" in brief
        assert "QUALITY BAR" in brief
        assert len(brief) <= 3600


def test_web_learner_url_allowlist():
    assert _is_allowed_url("https://en.wikipedia.org/w/api.php")
    assert _is_allowed_url("https://api.github.com/search/repositories")
    assert not _is_allowed_url("http://en.wikipedia.org/w/api.php")
    assert not _is_allowed_url("https://169.254.169.254/latest/meta-data/")
    assert not _is_allowed_url("https://evil.example.com/api")


def test_sentence_classification_extracts_controls_and_physics():
    sentences = [
        "Players move left and right with arrow keys or WASD and press spacebar to jump across gaps.",
        "The character experiences downward gravity acceleration and preserves horizontal momentum after jumping.",
        "Clearing waves awards a score multiplier and unlocks weapon upgrades.",
    ]
    controls, physics, mechanics = _classify_sentences(sentences)
    assert any("arrow keys" in s.lower() for s in controls)
    assert any("gravity" in s.lower() for s in physics)
    assert any("score multiplier" in s.lower() for s in mechanics)


@pytest.mark.asyncio
async def test_learn_from_similar_games_caches_and_renders(monkeypatch, tmp_path):
    calls = []

    class FakeResp:
        def __init__(self, payload: dict):
            self.status_code = 200
            self._payload = payload

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None, follow_redirects=False):
            calls.append((url, params))
            if "wikipedia.org" in url and (params or {}).get("list") == "search":
                return FakeResp({"query": {"search": [{"title": "Celeste (video game)"}]}})
            if "wikipedia.org" in url and (params or {}).get("prop") == "extracts":
                return FakeResp(
                    {
                        "query": {
                            "pages": {
                                "1": {
                                    "title": "Celeste (video game)",
                                    "extract": (
                                        "Players control Madeline using keyboard arrows or gamepad to run, climb, and dash. "
                                        "Physics include coyote time, jump buffering, and variable gravity arcs for tight platforming. "
                                        "Each chapter escalates difficulty with new stage hazards and collectibles."
                                    ),
                                }
                            }
                        }
                    }
                )
            if "api.github.com" in url:
                return FakeResp(
                    {
                        "items": [
                            {
                                "full_name": "example/html5-platformer",
                                "html_url": "https://github.com/example/html5-platformer",
                                "description": "Canvas platformer with fixed timestep physics and touch controls",
                                "topics": ["html5", "platformer", "physics"],
                            }
                        ]
                    }
                )
            return FakeResp({})

    monkeypatch.setattr("eightgen.core.engine.web_learner.httpx.AsyncClient", FakeClient)

    cache_dir = tmp_path / "cache"
    first = await learn_from_similar_games(
        "Make a Celeste style platformer",
        category="platformer",
        cache_dir=cache_dir,
    )
    assert first.from_cache is False
    assert first.has_findings is True
    assert any("Celeste" in title for title, _ in first.references)
    assert any("coyote time" in note.lower() for note in first.physics_notes)
    assert any("example/html5-platformer" in pat for pat in first.open_source_patterns)
    brief = first.render_brief()
    assert "Similar games studied online:" in brief
    assert "Observed physics & movement patterns:" in brief

    # Second call should hit local JSON cache without any HTTP requests.
    call_count_after_first = len(calls)
    second = await learn_from_similar_games(
        "Make a Celeste style platformer",
        category="platformer",
        cache_dir=cache_dir,
    )
    assert second.from_cache is True
    assert len(calls) == call_count_after_first
    assert json.loads((cache_dir / "learned_games.json").read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_learn_from_similar_games_offline_fallback(monkeypatch, tmp_path):
    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None, follow_redirects=False):
            raise RuntimeError("Network unreachable")

    monkeypatch.setattr("eightgen.core.engine.web_learner.httpx.AsyncClient", FailingClient)

    result = await learn_from_similar_games(
        "Space shooter",
        cache_dir=tmp_path / "cache",
    )
    assert isinstance(result, LearnedGameKnowledge)
    assert result.has_findings is False
    assert result.render_brief() == ""


@pytest.mark.asyncio
async def test_generator_injects_learned_research_into_prompt(monkeypatch, tmp_path):
    captured_prompts: list[str] = []

    class CapturingProvider(MockLLMProvider):
        async def generate(self, messages, **kwargs):
            captured_prompts.append(messages[-1].content)
            return await super().generate(messages, **kwargs)

    async def fake_learn(**kwargs):
        return LearnedGameKnowledge(
            query="celeste platformer",
            references=(("Celeste", "https://en.wikipedia.org/wiki/Celeste_(video_game)"),),
            physics_notes=("Coyote time and jump buffering keep ledge jumps crisp.",),
        )

    monkeypatch.setattr("eightgen.core.generator.learn_from_similar_games", fake_learn)

    settings = Settings(
        output_dir=tmp_path / "games",
        db_path=tmp_path / "games" / "8gen.db",
        auto_open=False,
        learn_from_web=True,
    )
    settings.ensure_directories()
    gen = GameGenerator(CapturingProvider(), PromptBuilder(), settings)
    html = await gen.generate("Make a celeste platformer")
    assert "<!DOCTYPE html>" in html
    assert captured_prompts
    assert "Coyote time and jump buffering keep ledge jumps crisp." in captured_prompts[0]
