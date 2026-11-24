"""Unit tests for prefixed environment settings and provider resolution."""

import pytest
from eightgen.config.loader import get_settings
from eightgen.config.settings import PROVIDER_AUTO, Settings
from eightgen.llm.factory import create_llm_provider
from eightgen.llm.gemini import GeminiProvider
from eightgen.llm.ollama import OllamaProvider


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Neutralize ambient provider credentials so tests are deterministic."""
    for var in (
        "EIGHTGEN_PROVIDER",
        "PROVIDER",
        "EIGHTGEN_GEMINI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "EIGHTGEN_GEMINI_PROXY_URL",
        "GEMINI_PROXY_URL",
        "EIGHTGEN_MODEL",
    ):
        monkeypatch.delenv(var, raising=False)


def test_env_prefix_is_used(monkeypatch):
    monkeypatch.setenv("EIGHTGEN_MODEL", "prefixed-model")
    monkeypatch.setenv("EIGHTGEN_TEMPERATURE", "0.42")
    settings = Settings(_env_file=None)
    assert settings.model == "prefixed-model"
    assert settings.temperature == pytest.approx(0.42)


def test_legacy_unprefixed_env_still_works(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "legacy-key")
    settings = Settings(_env_file=None)
    assert settings.gemini_api_key == "legacy-key"


def test_provider_defaults_to_auto():
    settings = Settings(_env_file=None)
    assert settings.provider == PROVIDER_AUTO


def test_auto_resolves_to_ollama_without_credentials():
    settings = Settings(_env_file=None)
    assert settings.resolved_provider == "ollama"
    assert isinstance(create_llm_provider(settings), OllamaProvider)


def test_auto_resolves_to_gemini_with_key(monkeypatch):
    monkeypatch.setenv("EIGHTGEN_GEMINI_API_KEY", "k")
    settings = Settings(_env_file=None)
    assert settings.resolved_provider == "gemini"
    assert isinstance(create_llm_provider(settings), GeminiProvider)


def test_explicit_gemini_without_key_raises(monkeypatch):
    monkeypatch.setenv("EIGHTGEN_PROVIDER", "gemini")
    settings = Settings(_env_file=None)
    with pytest.raises(ValueError, match="gemini"):
        create_llm_provider(settings)


def test_explicit_ollama_ignored_key():
    settings = Settings(provider="ollama", gemini_api_key="k", _env_file=None)
    assert settings.resolved_provider == "ollama"
    assert isinstance(create_llm_provider(settings), OllamaProvider)


def test_env_beats_config_file(tmp_path, monkeypatch):
    config = tmp_path / "8gen.toml"
    config.write_text('[llm]\nmodel = "from-file"\ntemperature = 0.11\n', encoding="utf-8")
    monkeypatch.setenv("EIGHTGEN_MODEL", "from-env")
    settings = get_settings(config_path=config)
    assert settings.model == "from-env"
    assert settings.temperature == pytest.approx(0.11)


def test_config_file_used_when_no_env(tmp_path, monkeypatch):
    config = tmp_path / "8gen.toml"
    config.write_text('[llm]\nmodel = "from-file"\n', encoding="utf-8")
    monkeypatch.delenv("EIGHTGEN_MODEL", raising=False)
    monkeypatch.delenv("MODEL", raising=False)
    settings = get_settings(config_path=config)
    assert settings.model == "from-file"
