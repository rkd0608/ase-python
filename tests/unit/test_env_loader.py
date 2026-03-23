"""Tests for ASE's minimal project-local `.env` loader."""

from __future__ import annotations

import os
from pathlib import Path

from ase.config.env_loader import load_local_dotenv


def test_load_local_dotenv_reads_nearest_parent(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    nested = project / "examples" / "demo"
    nested.mkdir(parents=True)
    (project / ".env").write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    loaded = load_local_dotenv(nested)
    assert loaded == project / ".env"
    assert os.environ["OPENAI_API_KEY"] == "test-key"


def test_load_local_dotenv_preserves_existing_values(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=file-value\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "existing")
    load_local_dotenv(tmp_path)
    assert os.environ["OPENAI_API_KEY"] == "existing"


def test_load_local_dotenv_parses_export_and_quotes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "export API_BASE='https://api.example.com'\nCOMMENTED=value # note\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("API_BASE", raising=False)
    monkeypatch.delenv("COMMENTED", raising=False)
    load_local_dotenv(tmp_path)
    assert os.environ["API_BASE"] == "https://api.example.com"
    assert os.environ["COMMENTED"] == "value"
