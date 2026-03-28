"""ase init — create a starter scenario file for new users."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ase.errors import CLIError

_console = Console()

_TEMPLATE = """scenario_id: {scenario_id}
name: {name}
agent:
  command: [python, agent.py]
agent_runtime:
  mode: adapter
  framework: custom
  adapter_name: custom-agent
  event_source: events.generated.jsonl
assertions:
  - evaluator: tool_called
    params:
      kind: http_api
      minimum: 1
"""


def run(
    target: Annotated[Path, typer.Argument(help="Scenario file path or stem to create.")],
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Replace an existing scenario file."),
    ] = False,
) -> None:
    """Create a minimal scenario so first-time users can start from a valid spec."""
    path = _normalize_target(target)
    if path.exists() and not overwrite:
        raise CLIError(f"scenario file already exists: {path}")
    scenario_id = path.stem.replace("_", "-")
    path.write_text(
        _TEMPLATE.format(scenario_id=scenario_id, name=scenario_id.replace("-", " ").title()),
        encoding="utf-8",
    )
    _console.print(f"created: {path}")


def _normalize_target(target: Path) -> Path:
    """Keep the command ergonomic by accepting either a path or a bare stem."""
    if target.exists() or target.suffix in {".yaml", ".yml"}:
        return target
    return target.with_suffix(".yaml")
