"""ase doctor — lightweight environment sanity checks.

This command exists to give operators a neutral boot-health signal without
requiring a full scenario run.
"""

from __future__ import annotations

import platform

from rich.console import Console
from rich.table import Table

_console = Console()


def run() -> None:
    """Show whether ASE's core imports and runtime prerequisites are available."""
    table = Table(title="ASE Doctor", expand=False)
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Details")
    for row in _rows():
        table.add_row(*row)
    _console.print(table)


def _rows() -> list[tuple[str, str, str]]:
    """Keep doctor output deterministic and safe for clean environment checks."""
    return [
        ("python", "ok", platform.python_version()),
        ("trace_model", *_import_status("ase.trace.model", "Trace")),
        ("config_loader", *_import_status("ase.config.loader", "load_config")),
        ("evaluation_engine", *_import_status("ase.evaluation.engine", "EvaluationEngine")),
    ]


def _import_status(module_name: str, attr_name: str) -> tuple[str, str]:
    """Convert importability into simple operator-facing status strings."""
    try:
        module = __import__(module_name, fromlist=[attr_name])
        getattr(module, attr_name)
    except (AttributeError, ImportError, ModuleNotFoundError) as exc:
        return ("fail", str(exc))
    return ("ok", "available")
