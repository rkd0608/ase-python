"""ase report — render one saved trace for operators and CI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ase.config.model import OutputFormat
from ase.errors import CLIError, TraceSerializationError
from ase.trace.model import Trace

_console = Console()


def run(
    trace_file: Annotated[Path, typer.Argument(help="Native ASE trace JSON file.")],
    output: Annotated[
        OutputFormat,
        typer.Option("--output", "-o", help="Output format."),
    ] = OutputFormat.TERMINAL,
    out_file: Annotated[
        Path | None,
        typer.Option("--out-file", "-f", help="Write the rendered report to this file."),
    ] = None,
) -> None:
    """Render a trace in a compact operator-facing or machine-readable format."""
    trace = _load_trace(trace_file)
    rendered = _render_trace(trace, output)
    if out_file is not None:
        suffix = "\n" if not rendered.endswith("\n") else ""
        out_file.write_text(rendered + suffix, encoding="utf-8")
        return
    _console.print(rendered)


def _load_trace(path: Path) -> Trace:
    """Load one native ASE trace with contextual parse errors."""
    try:
        return Trace.model_validate_json(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TraceSerializationError(f"failed to read trace file {path}: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise TraceSerializationError(f"failed to parse trace file {path}: {exc}") from exc


def _render_trace(trace: Trace, output: OutputFormat) -> str:
    """Choose the stable renderer for the requested output format."""
    if output == OutputFormat.JSON:
        return json.dumps(trace.model_dump(mode="json"), indent=2)
    if output == OutputFormat.MARKDOWN:
        return _to_markdown(trace)
    if output == OutputFormat.OTEL_JSON:
        return _to_otel_json(trace)
    if output == OutputFormat.TERMINAL:
        return _to_terminal_text(trace)
    raise CLIError(f"unsupported report output format: {output}")


def _to_terminal_text(trace: Trace) -> str:
    """Summarize the key execution, runtime, and evaluation facts for operators."""
    evaluation = trace.evaluation
    runtime = trace.runtime_provenance
    lines = [
        f"trace_id: {trace.trace_id}",
        f"scenario: {trace.scenario_id}",
        f"status: {trace.status}",
        f"runtime_mode: {runtime.mode if runtime else 'unknown'}",
        f"framework: {runtime.framework if runtime and runtime.framework else 'unknown'}",
        f"tool_calls: {trace.metrics.total_tool_calls}",
        f"llm_calls: {trace.metrics.total_llm_calls}",
    ]
    if evaluation is not None:
        assertions = (
            f"{evaluation.passed_count} passed / "
            f"{evaluation.failed_count} failed / "
            f"{evaluation.total} total"
        )
        lines.extend(
            [
                f"evaluation: {'passed' if evaluation.passed else 'failed'}",
                f"ase_score: {evaluation.ase_score:.2f}",
                f"assertions: {assertions}",
            ]
        )
    return "\n".join(lines)


def _to_markdown(trace: Trace) -> str:
    """Render a short Markdown report suitable for CI summaries and PR comments."""
    evaluation = trace.evaluation
    runtime = trace.runtime_provenance
    lines = [
        "# ASE Trace Report",
        "",
        f"- Trace ID: `{trace.trace_id}`",
        f"- Scenario: `{trace.scenario_id}`",
        f"- Status: `{trace.status}`",
        f"- Runtime: `{runtime.mode if runtime else 'unknown'}`",
        f"- Framework: `{runtime.framework if runtime and runtime.framework else 'unknown'}`",
        f"- Tool calls: `{trace.metrics.total_tool_calls}`",
    ]
    if evaluation is not None:
        lines.append(f"- ASE score: `{evaluation.ase_score:.2f}`")
    return "\n".join(lines)


def _to_otel_json(trace: Trace) -> str:
    """Delegate OTEL-like export to the trace interoperability layer."""
    from ase.trace.otel_export import to_otel_dict

    return json.dumps(to_otel_dict(trace), indent=2)
