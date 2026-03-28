from __future__ import annotations

import io
import re
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from ase.cli import test_cmd
from ase.cli.main import app

runner = CliRunner()


def _combined_output(result) -> str:
    exception = f"\n{result.exception}" if result.exception else ""
    return f"{result.output}{exception}"


def _assert_helpful_error(
    result, *, expected: str | None = None, pattern: str | None = None
) -> None:
    output = _combined_output(result)
    assert result.exit_code != 0, output
    assert "Traceback" not in output
    if expected is not None:
        assert expected in output
    if pattern is not None:
        assert re.search(pattern, output, flags=re.IGNORECASE), output


def test_test_nonexistent_yaml_reports_file_not_found() -> None:
    result = runner.invoke(app, ["test", "nonexistent.yaml"])
    _assert_helpful_error(result, pattern=r"file not found.*nonexistent\.yaml")


def test_test_malformed_yaml_reports_parse_line_number(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.yaml"
    malformed.write_text("scenario_id: demo\nname: bad\nagent: [\n", encoding="utf-8")

    result = runner.invoke(app, ["test", str(malformed)])
    _assert_helpful_error(result, pattern=r"failed to parse scenario|invalid yaml")
    assert re.search(r"line\s+\d+", _combined_output(result), flags=re.IGNORECASE)


def test_test_empty_assertions_can_still_complete_without_traceback(tmp_path: Path) -> None:
    scenario = tmp_path / "empty-assertions.yaml"
    scenario.write_text(
        "\n".join(
            [
                "spec_version: 1",
                "scenario_id: empty-assertions",
                "name: Empty assertions",
                "agent:",
                "  command: ['python', '-c', 'print(\"ok\")']",
                "assertions: []",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["test", str(scenario)])
    output = _combined_output(result)
    assert result.exit_code == 0, output
    assert "PASS empty-assertions" in output
    assert "evaluation=passed" in output
    assert "execution=passed" in output
    assert "Traceback" not in output


def test_watch_invalid_agent_target_times_out_gracefully() -> None:
    result = runner.invoke(app, ["watch", "--agent", "http://nothing:9999"])
    _assert_helpful_error(result, pattern=r"no such option: --agent")


def test_compare_nonexistent_dirs_reports_helpful_error() -> None:
    result = runner.invoke(app, ["compare", "dir1/", "dir2/"])
    _assert_helpful_error(result, pattern=r"failed to read trace file .*no such file or directory")


def test_compare_dirs_with_no_matching_scenarios_reports_helpful_message(tmp_path: Path) -> None:
    baseline = tmp_path / "dir1"
    candidate = tmp_path / "dir2"
    baseline.mkdir()
    candidate.mkdir()

    result = runner.invoke(app, ["compare", str(baseline), str(candidate)])
    _assert_helpful_error(result, pattern=r"failed to read trace file")
    assert re.search(r"is\s+a directory", _combined_output(result), flags=re.IGNORECASE)


def test_report_empty_directory_reports_no_traces(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty-dir"
    empty_dir.mkdir()

    result = runner.invoke(app, ["report", str(empty_dir)])
    _assert_helpful_error(result, pattern=r"failed to read trace file")
    assert re.search(r"is\s+a directory", _combined_output(result), flags=re.IGNORECASE)


def test_init_existing_name_requires_overwrite_confirmation(tmp_path: Path) -> None:
    existing = tmp_path / "existing-name"
    existing.write_text("already here\n", encoding="utf-8")

    result = runner.invoke(app, ["init", str(existing)])
    _assert_helpful_error(result, pattern=r"scenario file already exists")


def test_render_summary_marks_execution_failure_as_fail() -> None:
    trace = SimpleNamespace(
        trace_id="trace-x",
        scenario_id="scenario-x",
        status=SimpleNamespace(value="failed"),
        error_message="browser-use judge rejected result",
    )
    summary = SimpleNamespace(
        passed=True,
        ase_score=1.0,
        failing_evaluators=[],
    )
    buffer = io.StringIO()
    original_console = test_cmd._console
    try:
        from rich.console import Console

        test_cmd._console = Console(file=buffer, force_terminal=False)
        test_cmd._render_summary(trace, summary)
        output = buffer.getvalue()
    finally:
        test_cmd._console = original_console
    assert "FAIL scenario-x" in output
    assert "evaluation=passed execution=failed" in output
    assert "reason: execution failed: browser-use judge rejected result" in output
