"""Integration coverage for runnable framework-backed example agents."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / ".venv" / "bin" / "python"


def _project_env() -> dict[str, str]:
    """Keep subprocesses pointed at the in-repo ASE package."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return env


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run one command and return captured output for assertions."""
    return subprocess.run(
        command,
        cwd=ROOT,
        env=_project_env(),
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_success(result: subprocess.CompletedProcess[str]) -> None:
    """Surface stdout and stderr when an example validation step fails."""
    message = "\n".join([result.stdout.strip(), result.stderr.strip()]).strip()
    assert result.returncode == 0, message


def _assert_python_example(example_name: str, module_name: str) -> None:
    """Run and certify one Python framework example."""
    pytest.importorskip(module_name)
    example_dir = ROOT / "examples" / example_name
    event_file = example_dir / "events.generated.jsonl"
    event_file.unlink(missing_ok=True)
    _assert_success(
        _run(
            [
                str(PYTHON),
                str(example_dir / "agent.py"),
                "--events-out",
                str(event_file),
            ]
        )
    )
    _assert_success(
        _run(
            [
                str(PYTHON),
                "-m",
                "ase.cli.main",
                "adapter",
                "verify",
                str(event_file),
            ]
        )
    )
    _assert_success(
        _run(
            [
                str(PYTHON),
                "-m",
                "ase.cli.main",
                "certify",
                str(example_dir / "manifest.yaml"),
            ]
        )
    )


def _assert_scenario_test(example_name: str) -> None:
    """Run one example through `ase test` as the operator-facing workflow."""
    example_dir = ROOT / "examples" / example_name
    _assert_success(
        _run(
            [
                str(PYTHON),
                "-m",
                "ase.cli.main",
                "test",
                str(example_dir / "scenario.yaml"),
            ]
        )
    )


def test_openai_agents_python_example_certifies() -> None:
    _assert_python_example("openai-agents-python", "agents")


def test_openai_agents_python_example_supports_ase_test() -> None:
    pytest.importorskip("agents")
    _assert_scenario_test("openai-agents-python")


def test_langgraph_python_example_certifies() -> None:
    _assert_python_example("langgraph-python", "langgraph")


def test_langgraph_python_example_supports_ase_test() -> None:
    pytest.importorskip("langgraph")
    _assert_scenario_test("langgraph-python")


def test_pydantic_ai_python_example_certifies() -> None:
    _assert_python_example("pydantic-ai-python", "pydantic_ai")


def test_pydantic_ai_python_example_supports_ase_test() -> None:
    pytest.importorskip("pydantic_ai")
    _assert_scenario_test("pydantic-ai-python")


def test_openai_agents_typescript_example_certifies() -> None:
    if shutil.which("node") is None:
        pytest.skip("node is required for the typescript example")
    example_dir = ROOT / "examples" / "openai-agents-typescript"
    if not (example_dir / "node_modules").exists():
        pytest.skip("npm install has not been run for the typescript example")
    event_file = example_dir / "events.generated.jsonl"
    event_file.unlink(missing_ok=True)
    _assert_success(
        _run(["node", str(example_dir / "agent.ts"), "--events-out", str(event_file)])
    )
    _assert_success(
        _run(
            [
                str(PYTHON),
                "-m",
                "ase.cli.main",
                "adapter",
                "verify",
                str(event_file),
            ]
        )
    )
    _assert_success(
        _run(
            [
                str(PYTHON),
                "-m",
                "ase.cli.main",
                "certify",
                str(example_dir / "manifest.yaml"),
            ]
        )
    )


def test_openai_agents_typescript_example_supports_ase_test() -> None:
    if shutil.which("node") is None:
        pytest.skip("node is required for the typescript example")
    example_dir = ROOT / "examples" / "openai-agents-typescript"
    if not (example_dir / "node_modules").exists():
        pytest.skip("npm install has not been run for the typescript example")
    _assert_scenario_test("openai-agents-typescript")


def test_instrumented_python_example_supports_ase_test() -> None:
    _assert_scenario_test("instrumented-python")


def test_mcp_python_example_certifies() -> None:
    _assert_python_example("mcp-python", "mcp")


def test_mcp_python_example_supports_ase_test() -> None:
    _assert_scenario_test("mcp-python")
