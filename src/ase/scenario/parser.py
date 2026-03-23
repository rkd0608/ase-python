"""YAML parser for ASE scenarios."""

from __future__ import annotations

from pathlib import Path

import yaml

from ase.errors import ConfigError
from ase.scenario.model import ScenarioConfig

_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "ase_scenario.schema.json"


def parse_file(path: Path) -> ScenarioConfig:
    """Load one YAML scenario file and attach its source path metadata."""
    if not path.exists():
        raise ConfigError(f"failed to parse scenario: file not found {path}")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"failed to parse scenario: could not read {path}: {exc}") from exc
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"failed to parse scenario: invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"failed to parse scenario: root must be a mapping in {path}")
    run_metadata = dict(data.get("run_metadata") or {})
    run_metadata.setdefault("source", str(path.resolve()))
    data["run_metadata"] = run_metadata
    try:
        return ScenarioConfig.model_validate(data)
    except Exception as exc:
        raise ConfigError(f"failed to parse scenario: invalid spec in {path}: {exc}") from exc


def schema_path() -> Path:
    """Return the public scenario schema location in the repo."""
    return _SCHEMA_PATH
