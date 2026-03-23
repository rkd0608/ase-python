"""ase certify — validate a manifest and emit certification output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from ase.conformance.service import certify_manifest, load_manifest, sign_result
from ase.errors import ConformanceError

_console = Console()


def run(
    manifest: Annotated[Path, typer.Argument(help="Conformance manifest to certify.")],
    out_file: Annotated[
        Path | None,
        typer.Option("--out-file", "-f", help="Write certification JSON to this file."),
    ] = None,
    signing_key_env: Annotated[
        str | None,
        typer.Option("--signing-key-env", help="Env var containing the HMAC signing key."),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Render all certification checks."),
    ] = False,
) -> None:
    """Run a conformance manifest and emit a certification result."""
    try:
        loaded = load_manifest(manifest)
        result = sign_result(certify_manifest(loaded, manifest), signing_key_env=signing_key_env)
    except ConformanceError as exc:
        _console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if out_file is not None:
        out_file.write_text(json.dumps(result.model_dump(), indent=2) + "\n", encoding="utf-8")
    _render_result(result, verbose)
    if not result.passed:
        raise typer.Exit(code=1)


def _render_result(result: object, verbose: bool) -> None:
    """Render a compact certification summary with optional detailed checks."""
    from ase.conformance.model import ConformanceResult

    assert isinstance(result, ConformanceResult)
    status = "[green]passed[/green]" if result.passed else "[red]failed[/red]"
    _console.print(f"framework: {result.framework or 'unknown'}")
    _console.print(f"adapter:   {result.adapter_name}")
    _console.print(f"bundle:    {result.bundle_family}@{result.bundle_version}")
    _console.print(f"level:     {result.certification_level.value}")
    _console.print(f"status:    {status}")
    if not verbose and result.passed:
        return
    table = Table(title="Certification Checks")
    table.add_column("Case")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Message")
    for check in result.checks:
        table.add_row(
            check.case_id,
            check.check_id,
            "passed" if check.passed else "failed",
            check.message,
        )
    _console.print(table)
