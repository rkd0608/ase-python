from __future__ import annotations

from pathlib import Path

import pytest

from ase.errors import CLIError
from ase.examples_matrix import _require_repo_checkout, _validate_examples


def test_validate_examples_rejects_unknown_names() -> None:
    with pytest.raises(CLIError, match="unknown example names: nope"):
        _validate_examples(["nope"])


def test_require_repo_checkout_fails_without_repo_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_root = Path("/tmp/ase-wheel-layout")
    monkeypatch.setattr("ase.examples_matrix.ROOT", fake_root)
    monkeypatch.setattr("ase.examples_matrix.PYTHON", fake_root / ".venv" / "bin" / "python")
    with pytest.raises(CLIError, match="requires the ASE source checkout"):
        _require_repo_checkout()
