"""Fetch and bootstrap upstream framework repos for ASE validation.

This keeps the public ASE repository lightweight by materializing third-party
framework repos on demand into `.upstream/`, rather than committing them into
the main tree.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / ".upstream"


class UpstreamSpec(BaseModel):
    """Describe one fetchable upstream validation target."""

    name: str
    repo_url: str
    kind: str
    python_project: str | None = None


SPECS = {
    "openai-agents-python": UpstreamSpec(
        name="openai-agents-python",
        repo_url="https://github.com/openai/openai-agents-python.git",
        kind="python",
        python_project=".",
    ),
    "langgraph-python": UpstreamSpec(
        name="langgraph-python",
        repo_url="https://github.com/langchain-ai/langgraph.git",
        kind="python",
        python_project="libs/langgraph",
    ),
    "pydantic-ai-python": UpstreamSpec(
        name="pydantic-ai-python",
        repo_url="https://github.com/pydantic/pydantic-ai.git",
        kind="python",
        python_project=".",
    ),
    "openai-agents-js": UpstreamSpec(
        name="openai-agents-js",
        repo_url="https://github.com/openai/openai-agents-js.git",
        kind="node",
    ),
}

CHECKOUT_NAMES = {
    "openai-agents-python": "openai-agents-python",
    "langgraph-python": "langgraph",
    "pydantic-ai-python": "pydantic-ai",
    "openai-agents-js": "openai-agents-js",
}


def main() -> int:
    """Bootstrap one or more upstream repos for validation workflows."""
    args = _parse_args()
    for framework in _selected_frameworks(args.framework):
        spec = SPECS[framework]
        checkout = _ensure_checkout(args.root, spec)
        if spec.kind == "python":
            _bootstrap_python(checkout, args.python, spec)
        else:
            _bootstrap_node(checkout)
    return 0


def _parse_args() -> argparse.Namespace:
    """Parse bootstrap options for upstream validation workspaces."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--framework",
        action="append",
        choices=sorted(SPECS),
        help="Framework(s) to bootstrap. Defaults to all.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="Workspace root for fetched upstream repos.",
    )
    parser.add_argument(
        "--python",
        default=_default_upstream_python(),
        help="Python interpreter used to create upstream validation venvs.",
    )
    return parser.parse_args()


def _selected_frameworks(frameworks: list[str] | None) -> list[str]:
    """Return the requested framework set in deterministic order."""
    if frameworks:
        return frameworks
    return list(SPECS)


def _ensure_checkout(root: Path, spec: UpstreamSpec) -> Path:
    """Clone one upstream repo if it does not already exist locally."""
    root.mkdir(parents=True, exist_ok=True)
    checkout = root / CHECKOUT_NAMES[spec.name]
    if checkout.exists():
        print(f"using existing checkout: {checkout}")
        return checkout
    _run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            spec.repo_url,
            str(checkout),
        ],
        cwd=ROOT,
    )
    return checkout


def _bootstrap_python(checkout: Path, python_bin: str, spec: UpstreamSpec) -> None:
    """Create a validation venv and install one Python upstream repo editable."""
    venv_dir = checkout / ".venv"
    if not venv_dir.exists():
        _run([python_bin, "-m", "venv", str(venv_dir)], cwd=ROOT)
    pip_bin = venv_dir / "bin" / "pip"
    _run([str(pip_bin), "install", "--upgrade", "pip"], cwd=checkout)
    _run([str(pip_bin), "install", "-e", str(ROOT)], cwd=ROOT)
    project_root = _python_project_root(checkout, spec)
    _run([str(pip_bin), "install", "-e", str(project_root)], cwd=project_root)


def _bootstrap_node(checkout: Path) -> None:
    """Install the Node workspace and build the core package needed by ASE."""
    pnpm = shutil.which("pnpm")
    if pnpm is None:
        raise SystemExit("pnpm is required to bootstrap openai-agents-js")
    _run([pnpm, "install"], cwd=checkout)
    _run([pnpm, "-F", "@openai/agents-core", "build"], cwd=checkout)


def _run(command: list[str], cwd: Path) -> None:
    """Run one bootstrap command and fail with context when it errors."""
    print("+", " ".join(command))
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"command failed in {cwd}: {' '.join(command)}")


def _default_upstream_python() -> str:
    """Prefer Python 3.12 for upstream frameworks when it is available."""
    return shutil.which("python3.12") or sys.executable


def _python_project_root(checkout: Path, spec: UpstreamSpec) -> Path:
    """Resolve the installable Python project root inside one upstream repo."""
    if spec.python_project is None:
        return checkout
    return checkout / spec.python_project


if __name__ == "__main__":
    raise SystemExit(main())
