"""Configuration discovery and loading for ASE commands.

The CLI needs one predictable config flow: walk upward for `ase.yaml`, load it
if present, and otherwise return defaults. Keeping this logic in one module
avoids every command reimplementing file discovery and error handling.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ase.config.model import ASEConfig
from ase.errors import ConfigError

CONFIG_FILE_NAME = "ase.yaml"


def find_config_file(start: Path | None = None) -> Path | None:
    """Search upward so ASE works from nested example and project directories."""
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        candidate = directory / CONFIG_FILE_NAME
        if candidate.exists():
            return candidate
    return None


def load_config(path: Path | None = None) -> ASEConfig:
    """Return validated config or defaults when no project config exists."""
    config_path = path or find_config_file()
    if config_path is None:
        return ASEConfig()
    data = _read_config_dict(config_path)
    config = _validate_config(data, config_path)
    _load_declared_env_files(config_path, config)
    return config


def _read_config_dict(path: Path) -> dict[str, object]:
    """Translate YAML into a plain mapping with contextual parse errors."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"failed to read config {path}: {exc}") from exc
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"failed to parse config {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"invalid config {path}: root must be a mapping")
    return data


def _validate_config(data: dict[str, object], path: Path) -> ASEConfig:
    """Centralize model validation so config errors stay user-readable."""
    try:
        return ASEConfig.model_validate(data)
    except Exception as exc:
        raise ConfigError(f"invalid config {path}: {exc}") from exc


def _load_declared_env_files(config_path: Path, config: ASEConfig) -> None:
    """Load configured env files relative to the config directory in order."""
    from ase.config.env_loader import _parse_env_line
    base_dir = config_path.parent
    for relative in config.env_files:
        env_path = base_dir / relative
        if not env_path.exists():
            continue
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise ConfigError(f"failed to read env file {env_path}: {exc}") from exc
        for line in lines:
            parsed = _parse_env_line(line)
            if parsed is None:
                continue
            key, value = parsed
            import os
            os.environ[key] = value
