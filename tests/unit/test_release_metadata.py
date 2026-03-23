from __future__ import annotations

from pathlib import Path


def test_pyproject_uses_publishable_package_name() -> None:
    root = Path(__file__).resolve().parents[2]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "ase-python"' in pyproject
    assert '[project.scripts]' in pyproject
    assert 'ase = "ase.cli.main:app"' in pyproject


def test_publish_workflow_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow = root / ".github" / "workflows" / "publish-pypi.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "gh-action-pypi-publish" in text
    assert "https://pypi.org/project/ase-python/" in text


def test_pypi_readme_exists() -> None:
    root = Path(__file__).resolve().parents[2]
    readme = root / "README_PYPI.md"
    text = readme.read_text(encoding="utf-8")
    assert "pip install ase-python" in text
