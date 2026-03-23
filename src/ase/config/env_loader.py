"""Minimal `.env` loader used to keep CLI startup dependency-free.

ASE only needs project-local environment bootstrapping, not the full feature
surface of a third-party dotenv package. Keeping this logic in-repo avoids
startup failures caused by unrelated environment plugins or broken installs.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path

from ase.errors import ConfigError

ENV_FILE_NAME = ".env"


def load_local_dotenv(start: Path | None = None) -> Path | None:
    """Load the nearest project `.env` without overriding existing variables."""
    env_path = _find_dotenv(start or Path.cwd())
    if env_path is None:
        return None
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigError(f"failed to read env file {env_path}: {exc}") from exc
    for line in lines:
        parsed = _parse_env_line(line)
        if parsed is None:
            continue
        key, value = parsed
        os.environ.setdefault(key, value)
    return env_path


def _find_dotenv(start: Path) -> Path | None:
    """Search upward so ASE commands work from example and subdirectories."""
    current = start.resolve()
    for directory in [current, *current.parents]:
        candidate = directory / ENV_FILE_NAME
        if candidate.exists():
            return candidate
    return None


def _parse_env_line(line: str) -> tuple[str, str] | None:
    """Handle the simple KEY=VALUE syntax ASE documents for local setup."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped.removeprefix("export ").strip()
    if "=" not in stripped:
        return None
    key, raw_value = stripped.split("=", 1)
    key = key.strip()
    value = _normalize_value(raw_value.strip())
    return (key, value) if key else None


def _normalize_value(raw_value: str) -> str:
    """Preserve quoted values while allowing inline comments on bare values."""
    if not raw_value:
        return ""
    if raw_value[0] in {"'", '"'}:
        try:
            return shlex.split(raw_value)[0]
        except ValueError:
            return raw_value.strip("'\"")
    return raw_value.split(" #", 1)[0].strip()
