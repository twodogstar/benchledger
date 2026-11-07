"""Settings: where data lives and how the server listens.

Order of precedence (highest first):
  1. Environment variables  BENCHLEDGER_DATA_DIR, BENCHLEDGER_HOST, BENCHLEDGER_PORT
  2. Config file            $BENCHLEDGER_CONFIG, else ~/.config/benchledger/config.toml
  3. Built-in defaults      ~/benchledger-data, 127.0.0.1, 8765
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATA_DIR = "~/benchledger-data"
DEFAULT_HOST = "127.0.0.1"  # this machine only (requirement N1)
DEFAULT_PORT = 8765


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT

    @property
    def database_path(self) -> Path:
        return self.data_dir / "benchledger.db"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.database_path}"


def default_config_file(env: Mapping[str, str]) -> Path:
    base = env.get("XDG_CONFIG_HOME") or "~/.config"
    return Path(base).expanduser() / "benchledger" / "config.toml"


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build Settings from defaults, the config file and environment variables."""
    env = os.environ if env is None else env

    config_path = Path(env.get("BENCHLEDGER_CONFIG") or default_config_file(env)).expanduser()
    file_values: dict = {}
    if config_path.is_file():
        with config_path.open("rb") as f:
            file_values = tomllib.load(f)

    data_dir = env.get("BENCHLEDGER_DATA_DIR") or file_values.get("data_dir") or DEFAULT_DATA_DIR
    host = env.get("BENCHLEDGER_HOST") or file_values.get("host") or DEFAULT_HOST
    port = int(env.get("BENCHLEDGER_PORT") or file_values.get("port") or DEFAULT_PORT)

    if not 1 <= port <= 65535:
        raise ValueError(f"port must be between 1 and 65535, got {port}")

    return Settings(data_dir=Path(data_dir).expanduser().resolve(), host=str(host), port=port)
