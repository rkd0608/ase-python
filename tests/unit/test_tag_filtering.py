from __future__ import annotations

from pathlib import Path

from ase.cli import test_cmd
from ase.reporting.terminal import render_suite_header


def _write_scenario(path: Path, scenario_id: str, tags: list[str]) -> None:
    path.write_text(
        "\n".join(
            [
                f"scenario_id: {scenario_id}",
                f"name: {scenario_id}",
                "agent:",
                "  command: [python, agent.py]",
                "agent_runtime:",
                "  mode: adapter",
                "  event_source: events.generated.jsonl",
                "assertions: []",
                "tags:",
                *[f"  - {tag}" for tag in tags],
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_no_tag_filter_runs_all(tmp_path: Path) -> None:
    _write_scenario(tmp_path / "a.yaml", "a", ["tool_use"])
    _write_scenario(tmp_path / "b.yaml", "b", ["safety"])
    paths = test_cmd._collect_scenario_paths([tmp_path])
    filtered = test_cmd._filter_by_tags(paths, [])
    assert len(paths) == 2
    assert len(filtered) == 2


def test_single_tag_filters(tmp_path: Path) -> None:
    _write_scenario(tmp_path / "a.yaml", "a", ["tool_use"])
    _write_scenario(tmp_path / "b.yaml", "b", ["safety"])
    paths = test_cmd._collect_scenario_paths([tmp_path])
    filtered = test_cmd._filter_by_tags(paths, ["tool_use"])
    assert [path.name for path in filtered] == ["a.yaml"]


def test_multiple_tags_or_logic(tmp_path: Path) -> None:
    _write_scenario(tmp_path / "a.yaml", "a", ["tool_use"])
    _write_scenario(tmp_path / "b.yaml", "b", ["safety"])
    _write_scenario(tmp_path / "c.yaml", "c", ["correctness"])
    paths = test_cmd._collect_scenario_paths([tmp_path])
    filtered = test_cmd._filter_by_tags(paths, ["tool_use", "safety"])
    assert {path.name for path in filtered} == {"a.yaml", "b.yaml"}


def test_unknown_tag_runs_nothing(tmp_path: Path) -> None:
    _write_scenario(tmp_path / "a.yaml", "a", ["tool_use"])
    paths = test_cmd._collect_scenario_paths([tmp_path])
    filtered = test_cmd._filter_by_tags(paths, ["nonexistent"])
    assert filtered == []


def test_tags_shown_in_output() -> None:
    header = render_suite_header(
        roots=[Path("scenarios/")],
        selected_count=8,
        total_count=12,
        tags=["tool_use", "safety"],
    )
    assert "8 of 12 scenarios" in header
    assert "tags: tool_use, safety" in header
