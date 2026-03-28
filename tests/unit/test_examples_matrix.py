from __future__ import annotations

from pathlib import Path

import pytest

from ase.errors import CLIError
from ase.examples_matrix import (
    _require_repo_checkout,
    _upstream_checkout_ready,
    _validate_examples,
)


def test_validate_examples_rejects_unknown_names() -> None:
    with pytest.raises(CLIError, match="unknown example names: nope"):
        _validate_examples(["nope"])


def test_require_repo_checkout_fails_without_repo_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_root = Path("/tmp/ase-wheel-layout")
    monkeypatch.setattr("ase.examples_matrix.ROOT", fake_root)
    with pytest.raises(CLIError, match="requires the ASE source checkout"):
        _require_repo_checkout()


def test_upstream_checkout_ready_requires_bootstrap_artifacts(tmp_path: Path) -> None:
    checkout = tmp_path / "openai-agents-python"
    checkout.mkdir()
    assert not _upstream_checkout_ready("openai-agents-python", checkout)
    python_bin = checkout / ".venv" / "bin" / "python"
    python_bin.parent.mkdir(parents=True)
    python_bin.write_text("", encoding="utf-8")
    assert _upstream_checkout_ready("openai-agents-python", checkout)


def test_upstream_js_checkout_ready_requires_node_modules(tmp_path: Path) -> None:
    checkout = tmp_path / "openai-agents-js"
    checkout.mkdir()
    assert not _upstream_checkout_ready("openai-agents-js", checkout)
    (checkout / "node_modules").mkdir()
    assert _upstream_checkout_ready("openai-agents-js", checkout)
