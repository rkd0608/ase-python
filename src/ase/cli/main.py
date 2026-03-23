"""ASE CLI entry point.

Defines the top-level Typer app and registers all sub-commands.
Run via:
  ase watch | test | compare | report | init | history | doctor
  ase spec | baseline | adapter | replay | import | certify
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Annotated

import typer

from ase.config.env_loader import load_local_dotenv
from ase.config.model import OutputFormat

# Load .env from the project root (or any parent directory) before any command
# runs. Keeping this in-repo avoids CLI boot failures caused by broken optional
# dotenv/plugin installs in the user's environment.
load_local_dotenv()

app = typer.Typer(
    name="ase",
    help="Agent Simulation Engine — pytest for AI agent tool calls.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


def _run_test(
    scenario: Annotated[
        list[Path] | None,
        typer.Argument(help="Scenario YAML file(s) or directories to run."),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to ase.yaml config file."),
    ] = None,
    output: Annotated[
        OutputFormat | None,
        typer.Option("--output", "-o", help="Output format."),
    ] = None,
    out_file: Annotated[
        Path | None,
        typer.Option("--out-file", "-f", help="Write report to this file."),
    ] = None,
    fail_fast: Annotated[
        bool,
        typer.Option("--fail-fast", help="Stop after first failed scenario."),
    ] = False,
    workers: Annotated[
        int,
        typer.Option("--workers", "-w", help="Max concurrent scenarios."),
    ] = 4,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Stream agent stdout/stderr live to terminal."),
    ] = False,
) -> None:
    """Lazy-load ase test so non-proxy commands do not import mitmproxy."""
    from ase.cli.test_cmd import run
    run(scenario, config, output, out_file, fail_fast, workers, debug)


def _run_watch(
    ctx: typer.Context,
    command: Annotated[
        list[str] | None,
        typer.Argument(help="Agent command to run, e.g. python agent.py"),
    ] = None,
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Proxy port to listen on."),
    ] = 0,
    timeout: Annotated[
        int,
        typer.Option("--timeout", "-t", help="Max seconds to wait for agent."),
    ] = 120,
) -> None:
    """Lazy-load ase watch so the proxy stack is optional at import time."""
    from ase.cli.watch import run
    run(ctx, command, port, timeout)


def _run_doctor() -> None:
    """Lazy-load ase doctor so core CLI boot is resilient to optional modules."""
    from ase.cli.doctor_cmd import run
    run()


def _register_command(name: str, module_path: str, attr: str = "run") -> None:
    """Register one command only when its module is importable in this env."""
    try:
        module = import_module(module_path)
    except ImportError:
        return
    app.command(name)(getattr(module, attr))


def _register_typer(name: str, module_path: str, attr: str = "app") -> None:
    """Register one Typer sub-app only when its module is importable."""
    try:
        module = import_module(module_path)
    except ImportError:
        return
    app.add_typer(getattr(module, attr), name=name)


app.command("watch")(_run_watch)
app.command("test")(_run_test)
app.command("doctor")(_run_doctor)
_register_command("compare", "ase.cli.compare")
_register_command("report", "ase.cli.report")
_register_command("certify", "ase.cli.certify_cmd")
_register_command("replay", "ase.cli.replay_cmd")
_register_command("init", "ase.cli.init_cmd")
_register_command("history", "ase.cli.history_cmd")
_register_typer("spec", "ase.cli.spec_cmd")
_register_typer("baseline", "ase.cli.baseline_cmd")
_register_typer("adapter", "ase.cli.adapter_cmd")
_register_typer("examples", "ase.cli.examples_cmd")
_register_typer("import", "ase.cli.import_cmd")


def main() -> None:
    """Entry point called by the `ase` console script."""
    app()


if __name__ == "__main__":
    main()
