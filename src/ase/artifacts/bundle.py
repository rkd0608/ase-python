"""CI-friendly suite artifact bundles for ASE runs."""

from __future__ import annotations

import json
import time
from pathlib import Path

from pydantic import BaseModel, Field

from ase.config.model import OutputFormat
from ase.errors import TraceSerializationError
from ase.trace.model import Trace


class ScenarioArtifact(BaseModel):
    """Summarize one scenario run inside a suite artifact bundle."""

    scenario_id: str
    scenario_name: str
    scenario_path: str
    trace_id: str
    trace_path: str | None = None
    execution_status: str
    run_result: str
    ase_checks: str
    ase_score: float
    run_type: str
    framework: str | None = None
    tool_calls: int
    llm_calls: int
    main_reason: str | None = None
    baseline_trace_id: str | None = None
    baseline_regression: bool = False
    regression_summary: str | None = None


class SuiteArtifact(BaseModel):
    """Represent a suite-level artifact bundle for CI and local review."""

    bundle_version: int = 1
    suite_id: str
    generated_at_ms: float = Field(default_factory=lambda: time.time() * 1000)
    roots: list[str] = Field(default_factory=list)
    output_format: str = "terminal"
    run_result: str = "passed"
    checks_result: str = "not run"
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    regression_count: int = 0
    scenarios: list[ScenarioArtifact] = Field(default_factory=list)


def build_suite_artifact(
    *,
    suite_id: str,
    roots: list[Path],
    output_format: OutputFormat | None,
    scenarios: list[ScenarioArtifact],
    regressions: int = 0,
) -> SuiteArtifact:
    """Build one suite artifact from scenario artifacts."""
    passed = sum(1 for item in scenarios if item.run_result == "passed")
    failed = len(scenarios) - passed
    if len(scenarios) == 0:
        checks_result = "not run"
    else:
        checks_passed = all(item.ase_checks.startswith("passed") for item in scenarios)
        checks_result = "passed" if checks_passed else "failed"
    return SuiteArtifact(
        suite_id=suite_id,
        roots=[str(path) for path in roots],
        output_format=(output_format.value if output_format is not None else "terminal"),
        run_result="passed" if failed == 0 else "failed",
        checks_result=checks_result,
        total_scenarios=len(scenarios),
        passed_scenarios=passed,
        failed_scenarios=failed,
        regression_count=regressions,
        scenarios=scenarios,
    )


def scenario_artifact_from_run(
    *,
    scenario_path: Path,
    trace: Trace | None,
    trace_id: str | None = None,
    trace_path: str | None = None,
    execution_status: str,
    run_result: str,
    ase_checks: str,
    ase_score: float,
    run_type: str,
    framework: str | None,
    tool_calls: int,
    llm_calls: int,
    main_reason: str | None,
    baseline_trace_id: str | None = None,
    baseline_regression: bool = False,
    regression_summary: str | None = None,
) -> ScenarioArtifact:
    """Convert one executed scenario into a serializable artifact entry."""
    return ScenarioArtifact(
        scenario_id=trace.scenario_id if trace is not None else trace_id or "unknown",
        scenario_name=trace.scenario_name if trace is not None else trace_id or "unknown",
        scenario_path=str(scenario_path),
        trace_id=trace.trace_id if trace is not None else trace_id or "unknown",
        trace_path=trace_path,
        execution_status=execution_status,
        run_result=run_result,
        ase_checks=ase_checks,
        ase_score=ase_score,
        run_type=run_type,
        framework=framework,
        tool_calls=tool_calls,
        llm_calls=llm_calls,
        main_reason=main_reason,
        baseline_trace_id=baseline_trace_id,
        baseline_regression=baseline_regression,
        regression_summary=regression_summary,
    )


def render_terminal(suite: SuiteArtifact) -> str:
    """Render one suite artifact for a terminal-friendly view."""
    lines = [
        "◆ ASE Test Suite Artifact",
        f"suite_id: {suite.suite_id}",
        f"run_result: {suite.run_result}",
        f"checks: {suite.checks_result}",
        f"scenarios: {suite.total_scenarios} "
        f"({suite.passed_scenarios} passed / {suite.failed_scenarios} failed)",
    ]
    if suite.regression_count:
        lines.append(f"regressions: {suite.regression_count}")
    for scenario in suite.scenarios:
        lines.append(
            f"- {scenario.scenario_id}: {scenario.run_result} "
            f"(execution {scenario.execution_status}, checks {scenario.ase_checks}, "
            f"score {scenario.ase_score:.2f})"
        )
        if scenario.main_reason:
            lines.append(f"  main_reason: {scenario.main_reason}")
        if scenario.regression_summary:
            lines.append(f"  regression: {scenario.regression_summary}")
    return "\n".join(lines)


def render_markdown(suite: SuiteArtifact) -> str:
    """Render one suite artifact for Markdown consumers."""
    from ase.reporting.markdown import suite_to_string

    return suite_to_string(suite)


def render_json(suite: SuiteArtifact) -> str:
    """Render one suite artifact as pretty JSON."""
    return json.dumps(suite.model_dump(mode="json"), indent=2)


def render_junit(suite: SuiteArtifact, traces: dict[str, Trace]) -> str:
    """Render one suite artifact as JUnit XML."""
    from ase.reporting.junit import suite_to_string

    return suite_to_string(suite, traces)


def write_bundle(
    bundle_dir: Path,
    suite: SuiteArtifact,
    traces: dict[str, Trace],
) -> None:
    """Write a self-contained suite artifact bundle to disk."""
    try:
        bundle_dir.mkdir(parents=True, exist_ok=True)
        (bundle_dir / "summary.json").write_text(render_json(suite) + "\n", encoding="utf-8")
        (bundle_dir / "report.md").write_text(render_markdown(suite) + "\n", encoding="utf-8")
        (bundle_dir / "report.txt").write_text(render_terminal(suite) + "\n", encoding="utf-8")
        (bundle_dir / "junit.xml").write_text(render_junit(suite, traces) + "\n", encoding="utf-8")
        for scenario in suite.scenarios:
            trace = traces.get(scenario.trace_id)
            if trace is None:
                continue
            trace_path = Path(scenario.trace_path) if scenario.trace_path else Path(
                trace_relative_path(scenario.scenario_id)
            )
            scenario_dir = bundle_dir / trace_path.parent
            scenario_dir.mkdir(parents=True, exist_ok=True)
            (scenario_dir / "trace.json").write_text(
                trace.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
            )
        if len(suite.scenarios) == 1:
            trace = traces.get(suite.scenarios[0].trace_id)
            if trace is not None:
                (bundle_dir / "trace.json").write_text(
                    trace.model_dump_json(indent=2) + "\n",
                    encoding="utf-8",
                )
    except OSError as exc:
        raise TraceSerializationError(
            f"failed to write suite artifact bundle {bundle_dir}: {exc}"
        ) from exc


def resolve_trace_path(path: Path) -> Path:
    """Resolve a trace path, including bundle directories with a trace.json payload."""
    if path.is_dir():
        bundle_trace = path / "trace.json"
        if bundle_trace.exists():
            return bundle_trace
    return path


def load_suite_artifact(path: Path) -> SuiteArtifact | None:
    """Load one suite artifact bundle summary from disk if present."""
    if not path.is_dir():
        return None
    summary_path = path / "summary.json"
    if not summary_path.exists():
        return None
    try:
        return SuiteArtifact.model_validate_json(summary_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TraceSerializationError(
            f"failed to read suite artifact {summary_path}: {exc}"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise TraceSerializationError(
            f"failed to parse suite artifact {summary_path}: {exc}"
        ) from exc


def _safe_name(value: str) -> str:
    """Make a filesystem-friendly name without changing semantics."""
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value)


def trace_relative_path(scenario_id: str) -> str:
    """Return the stable bundle-relative trace path for one scenario."""
    return f"traces/{_safe_name(scenario_id)}/trace.json"
