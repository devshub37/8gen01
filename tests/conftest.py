"""Test fixtures and mock utilities."""

import pytest
from pathlib import Path
from typing import AsyncGenerator, List, Any
from eightgen.config.settings import Settings
from eightgen.llm.base import LLMMessage, LLMProvider, LLMResponse
from eightgen.storage.database import Database
from eightgen.storage.repository import GameRepository

SAMPLE_VALID_GAME = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Asteroid Blast</title>
  <style>canvas { background: #000; display: block; margin: auto; }</style>
</head>
<body>
  <canvas id="c" width="800" height="600"></canvas>
  <script>
    const canvas = document.getElementById('c');
    const ctx = canvas.getContext('2d');
    let x = 100;
    function loop() {
      ctx.clearRect(0, 0, 800, 600);
      ctx.fillStyle = '#fff';
      ctx.fillRect(x, 100, 20, 20);
      requestAnimationFrame(loop);
    }
    window.addEventListener('keydown', (e) => { x += 5; });
    loop();
  </script>
</body>
</html>
"""


class MockLLMProvider(LLMProvider):
    """Mock LLM Provider for deterministic testing."""

    def __init__(self, response_text: str = ""):
        self.response_text = response_text or f"```html\n{SAMPLE_VALID_GAME}\n```"
        self.model = "mock-model"

    async def generate(self, messages: List[LLMMessage], **kwargs: Any) -> LLMResponse:
        return LLMResponse(content=self.response_text, model=self.model)

    async def stream(self, messages: List[LLMMessage], **kwargs: Any) -> AsyncGenerator[str, None]:
        chunk_size = 50
        for i in range(0, len(self.response_text), chunk_size):
            yield self.response_text[i:i + chunk_size]

    async def list_models(self) -> List[str]:
        return ["mock-model", "qwen2.5-coder"]

    async def is_healthy(self) -> bool:
        return True


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    """Fixture providing isolated temporary directories for storage."""
    games_dir = tmp_path / "games"
    db_file = tmp_path / "test_8gen.db"
    settings = Settings(
        output_dir=games_dir,
        db_path=db_file,
        auto_open=False,
        max_retries=2,
        learn_from_web=False,
    )
    settings.ensure_directories()
    return settings


@pytest.fixture
def repo(tmp_settings: Settings) -> GameRepository:
    """Fixture providing isolated repository."""
    db = Database(tmp_settings.db_path)
    return GameRepository(db, tmp_settings.output_dir)


@pytest.fixture
def mock_provider() -> MockLLMProvider:
    return MockLLMProvider()
