"""Configuration settings for 8Gen."""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load .env file if available
load_dotenv()


def is_vercel() -> bool:
    """Return True when running inside Vercel's serverless environment."""
    return bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))


def _default_provider() -> str:
    return os.getenv("EIGHTGEN_PROVIDER") or os.getenv("PROVIDER") or "gemini"


def _default_output_dir() -> Path:
    env_val = os.getenv("EIGHTGEN_OUTPUT_DIR") or os.getenv("OUTPUT_DIR")
    if env_val:
        return Path(env_val)
    return Path("/tmp/8gen/games") if is_vercel() else Path("./games")


def _default_db_path() -> Path:
    env_val = os.getenv("EIGHTGEN_DB_PATH") or os.getenv("DB_PATH")
    if env_val:
        return Path(env_val)
    return Path("/tmp/8gen/games/8gen.db") if is_vercel() else Path("./games/8gen.db")


class Settings(BaseSettings):
    """Application settings loaded from environment, config files, or defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # LLM Settings
    provider: str = Field(
        default_factory=_default_provider,
        description="LLM provider: 'gemini' or 'ollama'",
    )

    # Gemini Settings (Fast & High Playability)
    gemini_api_key: str = Field(
        default_factory=lambda: (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("EIGHTGEN_GEMINI_API_KEY")
            or ""
        ),
        description="Google Gemini API Key"
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
    timeout: float = Field(default=120.0, description="LLM HTTP timeout in seconds")
    max_retries: int = Field(default=3, description="Self-healing validation retry limit")

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

    # CLI & UI
    stream_output: bool = Field(default=True, description="Stream LLM generation directly to terminal")
    theme: str = Field(default="dark", description="Dashboard UI theme")

    def ensure_directories(self) -> None:
        """Ensure necessary storage directories exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def active_model_display(self) -> str:
        """Get human-readable display of current active model."""
        if self.provider == "gemini":
            return f"⚡ Gemini ({self.gemini_model})"
        return f"🦙 Ollama ({self.model})"
