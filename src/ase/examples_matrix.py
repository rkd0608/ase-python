"""Public example-matrix runner used by the CLI and repo scripts.

Keeping the matrix logic in the package makes example validation a supported
workflow rather than an internal maintenance script.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel

from ase.errors import CLIError

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / ".venv" / "bin" / "python"
SUPPORTED_EXAMPLES = (
    "instrumented-python",
    "mcp-python",
    "openai-agents-python",
    "langgraph-python",
    "pydantic-ai-python",
    "openai-agents-typescript",
)


class ExampleRunResult(BaseModel):
    """Outcome of validating one example through ASE's public workflows."""

    example_name: str
    passed: bool
    commands: list[list[str]]


def run_examples(example_names: list[str] | None = None) -> list[ExampleRunResult]:
    """Run the requested examples with the same commands users run manually."""
    _require_repo_checkout()
    selected = example_names or list(SUPPORTED_EXAMPLES)
    _validate_examples(selected)
    return [_run_example(name) for name in selected]


def _run_example(example_name: str) -> ExampleRunResult:
    """Execute the supported workflow for one example."""
    commands = _commands_for_example(example_name)
    for command in commands:
        _run(command, cwd=_working_directory(example_name, command))
    return ExampleRunResult(example_name=example_name, passed=True, commands=commands)


def _commands_for_example(example_name: str) -> list[list[str]]:
    """Return the public ASE commands for one example type."""
    scenario_path = f"examples/{example_name}/scenario.yaml"
    if example_name == "instrumented-python":
        return [[str(PYTHON), "-m", "ase.cli.main", "test", scenario_path]]
    if example_name == "openai-agents-typescript":
        _ensure_typescript_example_installed()
    manifest_path = f"examples/{example_name}/manifest.yaml"
    return [
        [str(PYTHON), "-m", "ase.cli.main", "test", scenario_path],
        [str(PYTHON), "-m", "ase.cli.main", "certify", manifest_path],
    ]


def _working_directory(example_name: str, command: list[str]) -> Path:
    """Run npm only inside the TypeScript example directory."""
    if command[:2] == ["npm", "install"]:
        return ROOT / "examples" / example_name
    return ROOT


def _ensure_typescript_example_installed() -> None:
    """Install local JS dependencies so the TS adapter example can run."""
    example_dir = ROOT / "examples" / "openai-agents-typescript"
    if (example_dir / "node_modules").exists():
        return
    if shutil.which("npm") is None:
        raise CLIError("npm is required to run the openai-agents-typescript example")
    _run(["npm", "ci"], cwd=example_dir)


def _run(command: list[str], cwd: Path) -> None:
    """Run one example command and fail with the captured ASE output."""
    result = subprocess.run(
        command,
        cwd=cwd,
        env=_project_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return
    message = "\n".join(
        [
            f"command failed: {' '.join(command)}",
            result.stdout.strip(),
            result.stderr.strip(),
        ]
    ).strip()
    raise CLIError(message)


def _project_env() -> dict[str, str]:
    """Keep matrix runs pinned to the in-repo ASE package and toolchain."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return env


def _validate_examples(example_names: list[str]) -> None:
    """Reject unknown example names before running subprocesses."""
    unsupported = sorted(set(example_names) - set(SUPPORTED_EXAMPLES))
    if unsupported:
        joined = ", ".join(unsupported)
        raise CLIError(f"unknown example names: {joined}")


def _require_repo_checkout() -> None:
    """Fail clearly when examples are invoked from a wheel install."""
    required_paths = [
        ROOT / "examples",
        ROOT / "validation",
        ROOT / "src",
        PYTHON,
    ]
    if all(path.exists() for path in required_paths):
        return
    raise CLIError(
        "ase examples run requires the ASE source checkout; "
        "clone https://github.com/rkd0608/ase-python and run it from the repo root"
    )
