"""ase report — render one saved trace for operators and CI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ase.config.model import OutputFormat
from ase.errors import CLIError, TraceSerializationError
from ase.reporting.junit import trace_to_string as junit_trace_to_string
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
    try:
        trace = _load_trace(trace_file)
        rendered = _render_trace(trace, output)
        if out_file is not None:
            suffix = "\n" if not rendered.endswith("\n") else ""
            out_file.write_text(rendered + suffix, encoding="utf-8")
            return
        _console.print(rendered)
    except (CLIError, TraceSerializationError) as exc:
        _console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


def _load_trace(path: Path) -> Trace:
    """Load one native ASE trace with contextual parse errors."""
    if path.is_dir():
        raise TraceSerializationError(f"failed to read trace file {path}: is a directory")
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
    if output == OutputFormat.JUNIT:
        return _to_junit(trace)
    if output == OutputFormat.TERMINAL:
        return _to_terminal_text(trace)
    raise CLIError(f"unsupported report output format: {output}")


def _to_terminal_text(trace: Trace) -> str:
    """Summarize the key execution, runtime, and evaluation facts for operators."""
    evaluation = trace.evaluation
    runtime = trace.runtime_provenance
    checks_status = _checks_status(trace)
    lines = [
        f"run_id: {trace.trace_id}",
        f"scenario: {trace.scenario_id}",
        f"run_result: {trace.status.value}",
        f"ase_checks: {checks_status}",
        f"run_type: {runtime.mode if runtime else 'unknown'}",
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
                f"ase_score: {evaluation.ase_score:.2f}",
                f"assertions: {assertions}",
            ]
        )
        if evaluation.failing_evaluators:
            lines.append("failing_evaluators: " + ", ".join(evaluation.failing_evaluators))
    if trace.error_message:
        lines.append(f"main_reason: {trace.error_message}")
    if evaluation is None:
        lines.append(
            "next_step: this replayed trace has no stored checks; if you ran 'ase test', "
            f"use 'ase history --trace-id {trace.trace_id}'"
        )
    return "\n".join(lines)


def _to_markdown(trace: Trace) -> str:
    """Render a short Markdown report suitable for CI summaries and PR comments."""
    evaluation = trace.evaluation
    runtime = trace.runtime_provenance
    execution_status = trace.status.value
    checks_status = _checks_status(trace)
    lines = [
        "# ASE Run Report",
        "",
        f"- Run ID: `{trace.trace_id}`",
        f"- Scenario: `{trace.scenario_id}`",
        f"- Run result: `{execution_status}`",
        f"- ASE checks: `{checks_status}`",
        f"- Run type: `{runtime.mode if runtime else 'unknown'}`",
        f"- Framework: `{runtime.framework if runtime and runtime.framework else 'unknown'}`",
        f"- Tool calls: `{trace.metrics.total_tool_calls}`",
    ]
    if evaluation is not None:
        lines.append(f"- ASE score: `{evaluation.ase_score:.2f}`")
        if evaluation.failing_evaluators:
            lines.append(
                "- Failing evaluators: `"
                + ", ".join(evaluation.failing_evaluators)
                + "`"
            )
    if trace.error_message:
        lines.append(f"- Main reason: `{trace.error_message}`")
    lines.extend(["", "## What Happened"])
    lines.extend(f"- {item}" for item in _what_happened(trace))
    lines.extend(["", "## Suggested Next Step"])
    lines.append(f"- { _next_step(trace) }")
    return "\n".join(lines)


def _to_otel_json(trace: Trace) -> str:
    """Delegate OTEL-like export to the trace interoperability layer."""
    from ase.trace.otel_export import to_otel_dict

    return json.dumps(to_otel_dict(trace), indent=2)


def _to_junit(trace: Trace) -> str:
    """Render persisted evaluation results as JUnit XML for CI consumers."""
    return junit_trace_to_string(trace)


def _evaluation_status(trace: Trace) -> str:
    """Return the persisted evaluation status when present."""
    if trace.evaluation is None:
        return "unknown"
    return "passed" if trace.evaluation.passed else "failed"


def _checks_status(trace: Trace) -> str:
    """Return a user-facing checks status string for stored or replayed traces."""
    if trace.evaluation is None:
        return "not included in this trace"
    return "passed" if trace.evaluation.passed else "failed"


def _what_happened(trace: Trace) -> list[str]:
    """Build a short narrative summary for operator-facing reports."""
    items = [
        f"ASE observed {trace.metrics.total_tool_calls} tool call(s).",
    ]
    if trace.evaluation is None:
        items.append("This report came from a replayed trace, so ASE checks are not attached here.")
    elif trace.evaluation.passed:
        items.append("ASE checks passed on the stored run.")
    else:
        items.append("ASE checks failed on the stored run.")
    if trace.status.value == "passed":
        items.append("The agent run completed successfully.")
    else:
        items.append(f"The agent run ended with status '{trace.status.value}'.")
    return items


def _next_step(trace: Trace) -> str:
    """Suggest the next most helpful command for understanding a run."""
    if trace.evaluation is None:
        return (
            "If this came from `ase test`, run "
            f"`ase history --trace-id {trace.trace_id}` to view the stored evaluated run."
        )
    return f"Run `ase history --trace-id {trace.trace_id}` for the full stored run details."
