"""Integration test for OllamaProvider against local Ollama instance.

Gated behind the ``integration`` marker and the ``OLLAMA_INTEGRATION=1``
environment variable so a default ``pytest`` run stays green without a local
Ollama daemon:

    OLLAMA_INTEGRATION=1 pytest -m integration
"""

import os

import pytest
from eightgen.llm.ollama import OllamaProvider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("OLLAMA_INTEGRATION", "").strip().lower() not in ("1", "true", "yes", "on"),
        reason="Ollama integration test; set OLLAMA_INTEGRATION=1 to run",
    ),
]


@pytest.mark.asyncio
async def test_ollama_connectivity():
    provider = OllamaProvider(base_url="http://localhost:11434")
    is_healthy = await provider.is_healthy()
    assert is_healthy is True, "Ollama must be reachable on http://localhost:11434"

    models = await provider.list_models()
    assert len(models) > 0, "At least one model should be downloaded in Ollama"

    resolved = await provider.resolve_model()
    assert resolved != ""
