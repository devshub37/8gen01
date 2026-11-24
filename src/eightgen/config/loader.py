"""Configuration loader and manager."""

import os
from pathlib import Path
import tomllib
from typing import Any, Dict
from eightgen.config.settings import Settings

# Bundled defaults ship with the package and sit at the bottom of the priority chain.
BUNDLED_DEFAULT_CONFIG = Path(__file__).parent / "default.toml"

DEFAULT_CONFIG_LOCATIONS = [
    Path("./8gen.toml"),
    Path.home() / ".config" / "eightgen" / "config.toml",
]

# Legacy (unprefixed) environment variables that still override config file values.
_LEGACY_ENV_ALIASES: Dict[str, tuple] = {
    "provider": ("PROVIDER",),
    "gemini_api_key": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "output_dir": ("OUTPUT_DIR",),
    "db_path": ("DB_PATH",),
}


def load_toml_config(path: Path) -> Dict[str, Any]:
    """Parse TOML configuration file flattening sections."""
    if not path.is_file():
        return {}
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        flattened: Dict[str, Any] = {}
        for key, val in data.items():
            if isinstance(val, dict):
                for sub_key, sub_val in val.items():
                    if sub_key == "provider":
                        flattened["provider"] = sub_val
                    elif sub_key == "ollama_url":
                        flattened["ollama_url"] = sub_val
                    elif sub_key == "model":
                        flattened["model"] = sub_val
                    elif sub_key == "temperature":
                        flattened["temperature"] = sub_val
                    elif sub_key == "timeout":
                        flattened["timeout"] = sub_val
                    elif sub_key == "max_retries":
                        flattened["max_retries"] = sub_val
                    elif sub_key == "output_dir":
                        flattened["output_dir"] = Path(sub_val)
                    elif sub_key == "db_path":
                        flattened["db_path"] = Path(sub_val)
                    elif sub_key == "host":
                        flattened["server_host"] = sub_val
                    elif sub_key == "port":
                        flattened["server_port"] = sub_val
                    elif sub_key == "auto_open":
                        flattened["auto_open"] = sub_val
                    elif sub_key == "stream_output":
                        flattened["stream_output"] = sub_val
                    elif sub_key == "theme":
                        flattened["theme"] = sub_val
                    else:
                        flattened[sub_key] = sub_val
            else:
                flattened[key] = val
        return flattened
    except Exception:
        return {}


def _env_supplies(key: str) -> bool:
    """True when an environment variable already provides this setting."""
    if os.getenv(f"EIGHTGEN_{key.upper()}") is not None:
        return True
    for alias in _LEGACY_ENV_ALIASES.get(key, ()):
        if os.getenv(alias):
            return True
    return False


def get_settings(config_path: Path | None = None, **overrides: Any) -> Settings:
    """Load settings with priority: overrides > environment > config file > bundled defaults."""
    defaults: Dict[str, Any] = load_toml_config(BUNDLED_DEFAULT_CONFIG)

    file_data: Dict[str, Any] = {}
    if config_path and Path(config_path).is_file():
        file_data = load_toml_config(Path(config_path))
    else:
        for loc in DEFAULT_CONFIG_LOCATIONS:
            if loc.is_file():
                file_data = load_toml_config(loc)
                break

    # Strip None overrides
    clean_overrides = {k: v for k, v in overrides.items() if v is not None}

    merged_data = {**defaults, **file_data, **clean_overrides}

    # Environment variables beat the config file; explicit overrides still win
    # over everything (they are passed as init kwargs, which pydantic prefers).
    file_level_keys = set(defaults) | set(file_data)
    for key in file_level_keys:
        if key in clean_overrides:
            continue
        if _env_supplies(key):
            merged_data.pop(key, None)

    settings = Settings(**merged_data)
    settings.ensure_directories()
    return settings
