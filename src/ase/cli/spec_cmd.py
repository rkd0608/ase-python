"""ase spec — validate scenarios and expose their JSON schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ase.scenario.parser import parse_file, schema_path

app = typer.Typer(help="Validate ASE scenarios and inspect the public schema.")
_console = Console()


@app.command("validate")
def validate(
    scenario: Annotated[Path, typer.Argument(help="Scenario YAML file to validate.")],
) -> None:
    """Validate one scenario file against ASE's current scenario model."""
    config = parse_file(scenario)
    _console.print(f"valid: {config.scenario_id}")


@app.command("print-schema")
def print_schema(
    kind: Annotated[
        str,
        typer.Option("--kind", help="scenario | conformance-manifest | conformance-result"),
    ] = "scenario",
    path: Annotated[bool, typer.Option("--path", help="Print the schema file path only.")] = False,
) -> None:
    """Print the public scenario schema or its repo path."""
    target = _schema_path(kind)
    if path:
        _console.print(str(target))
        return
    payload = json.loads(target.read_text(encoding="utf-8"))
    _console.print(json.dumps(payload, indent=2))


def _schema_path(kind: str) -> Path:
    """Resolve public schema aliases onto repo paths."""
    if kind == "scenario":
        return schema_path()
    root = schema_path().parent
    if kind == "conformance-manifest":
        return root / "ase_conformance_manifest.schema.json"
    if kind == "conformance-result":
        return root / "ase_conformance_result.schema.json"
    raise typer.BadParameter(f"unknown schema kind: {kind}")
