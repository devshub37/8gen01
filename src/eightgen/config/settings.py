"""Configuration settings for 8Gen."""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load .env file if available
load_dotenv()

# All settings read environment variables through the EIGHTGEN_ prefix
# (e.g. EIGHTGEN_MODEL, EIGHTGEN_SERVER_PORT). The names below are legacy,
# unprefixed aliases kept for backward compatibility.
_LEGACY_PROVIDER_ENV = "PROVIDER"
_LEGACY_GEMINI_KEY_ENV = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
_LEGACY_OUTPUT_DIR_ENV = "OUTPUT_DIR"
_LEGACY_DB_PATH_ENV = "DB_PATH"

PROVIDER_AUTO = "auto"
GEMINI_ALIASES = ("gemini", "google")
OLLAMA_ALIASES = ("ollama", "local")


def is_vercel() -> bool:
    """Return True when running inside Vercel's serverless environment."""
    return bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))


def _default_provider() -> str:
    """Fallback when neither the environment nor a config file selects a provider."""
    return os.getenv("EIGHTGEN_PROVIDER") or os.getenv(_LEGACY_PROVIDER_ENV) or PROVIDER_AUTO


def _default_output_dir() -> Path:
    env_val = os.getenv("EIGHTGEN_OUTPUT_DIR") or os.getenv(_LEGACY_OUTPUT_DIR_ENV)
    if env_val:
        return Path(env_val)
    return Path("/tmp/8gen/games") if is_vercel() else Path("./games")


def _default_db_path() -> Path:
    env_val = os.getenv("EIGHTGEN_DB_PATH") or os.getenv(_LEGACY_DB_PATH_ENV)
    if env_val:
        return Path(env_val)
    return Path("/tmp/8gen/games/8gen.db") if is_vercel() else Path("./games/8gen.db")


def _default_gemini_api_key() -> str:
    for env_name in ("EIGHTGEN_GEMINI_API_KEY", *_LEGACY_GEMINI_KEY_ENV):
        val = os.getenv(env_name)
        if val:
            return val
    return ""


class Settings(BaseSettings):
    """Application settings loaded from environment, config files, or defaults.

    Environment variables use the ``EIGHTGEN_`` prefix and take precedence
    over TOML configuration files (see ``eightgen.config.loader``).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="EIGHTGEN_",
        extra="ignore"
    )

    # LLM Settings
    provider: str = Field(
        default_factory=_default_provider,
        description=(
            "LLM provider selection: 'gemini', 'ollama', or 'auto' "
            "(auto picks Gemini when an API key is configured, otherwise Ollama)."
        ),
    )

    # Gemini Settings (Fast & High Playability)
    gemini_api_key: str = Field(
        default_factory=_default_gemini_api_key,
        description="Google Gemini API Key (EIGHTGEN_GEMINI_API_KEY or legacy GEMINI_API_KEY)"
    )
    gemini_model: str = Field(default="gemini-3-flash-preview", description="Gemini model name")
    gemini_proxy_url: Optional[str] = Field(
        default=None,
        description="Local OpenAI-compatible Gemini proxy URL (e.g. http://localhost:4981/openai/v1 or http://localhost:8081/v1)"
    )

    # Ollama Settings (Local fallback)
    ollama_url: str = Field(default="http://localhost:11434", description="Ollama API base URL")
    model: str = Field(
        default="huihui_ai/qwen2.5-coder-abliterate:7b",
        description="Ollama model name"
    )

    temperature: float = Field(default=0.7, description="Generation temperature (0.0 to 1.0)")
    timeout: float = Field(default=180.0, description="LLM HTTP timeout in seconds")
    max_retries: int = Field(default=3, description="Self-healing validation retry limit")

    # Generation quality gates
    js_syntax_check: bool = Field(
        default=True,
        description="Run JavaScript syntax checks (via node, when available) during validation",
    )
    smoke_test: bool = Field(
        default=False,
        description="Run a headless browser smoke test on generated games (requires playwright)",
    )

    # Storage Settings
    output_dir: Path = Field(
        default_factory=_default_output_dir,
        description="Directory to save generated games",
    )
    db_path: Path = Field(
        default_factory=_default_db_path,
        description="Path to SQLite metadata database",
    )

    # Server Settings
    server_host: str = Field(default="127.0.0.1", description="Web dashboard host")
    server_port: int = Field(default=8000, description="Web dashboard port")
    auto_open: bool = Field(default=True, description="Automatically open generated games in browser")

    # Server security (important for public deployments)
    api_token: Optional[str] = Field(
        default=None,
        description=(
            "Optional access token protecting the dashboard and all mutating API "
            "endpoints. Unset (empty) disables authentication, which is only "
            "appropriate for local single-user use."
        ),
    )
    cors_origins: str = Field(
        default="",
        description="Comma-separated origins allowed by CORS; empty means same-origin only",
    )
    rate_limit: int = Field(
        default=30,
        description="Max mutating API requests allowed per client per minute (0 disables)",
    )

    # CLI & UI
    stream_output: bool = Field(default=True, description="Stream LLM generation directly to terminal")
    theme: str = Field(default="dark", description="Dashboard UI theme")

    def ensure_directories(self) -> None:
        """Ensure necessary storage directories exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def provider_is_explicit(self) -> bool:
        """True when the user explicitly selected a provider (not auto-detection)."""
        return self.provider.strip().lower() in (*GEMINI_ALIASES, *OLLAMA_ALIASES)

    @property
    def resolved_provider(self) -> str:
        """The provider that will actually be used ('gemini' or 'ollama')."""
        name = self.provider.strip().lower()
        if name in GEMINI_ALIASES:
            return "gemini"
        if name in OLLAMA_ALIASES:
            return "ollama"
        # auto: prefer Gemini only when credentials exist, else local Ollama
        if self.gemini_api_key or self.gemini_proxy_url:
            return "gemini"
        return "ollama"

    @property
    def active_model_display(self) -> str:
        """Get human-readable display of current active model."""
        if self.resolved_provider == "gemini":
            return f"⚡ Gemini ({self.gemini_model})"
        return f"🦙 Ollama ({self.model})"
