"""Shared helpers for writing native traces and rendered outputs."""

from __future__ import annotations

from pathlib import Path

from ase.config.model import OutputFormat
from ase.reporting import json_report, markdown
from ase.trace.model import Trace
from ase.trace.otel_export import to_otel_dict
from ase.trace.serializer import write_to_file


def write_trace_artifacts(
    trace: Trace,
    *,
    trace_out: Path | None = None,
    output: OutputFormat | None = None,
    out_file: Path | None = None,
) -> None:
    """Write native traces and optional rendered outputs for CLI workflows."""
    if trace_out is not None:
        write_to_file(trace, trace_out)
    if output is None or out_file is None:
        return
    rendered = render_trace(trace, output)
    out_file.write_text(rendered + "\n", encoding="utf-8")


def render_trace(trace: Trace, output: OutputFormat) -> str:
    """Render one trace using the requested public output format."""
    if output == OutputFormat.JSON:
        return json_report.to_string(trace=trace)
    if output == OutputFormat.MARKDOWN:
        return markdown.to_string(trace=trace)
    if output == OutputFormat.OTEL_JSON:
        import json

        return json.dumps(to_otel_dict(trace), indent=2)
    return json_report.to_string(trace=trace)
