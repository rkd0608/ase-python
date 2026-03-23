from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_root_readme_exists() -> None:
    assert (ROOT / "README.md").exists()


def test_validation_scenarios_do_not_reference_external_repos() -> None:
    scenario_paths = sorted((ROOT / "validation" / "upstream").glob("*/ase-scenario.yaml"))
    assert scenario_paths
    for path in scenario_paths:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        command = " ".join(data["agent"]["command"])
        event_source = data["agent_runtime"]["event_source"]
        assert "external/" not in command
        assert event_source == "events.generated.jsonl"


def test_validation_manifests_use_local_relative_event_files() -> None:
    manifest_paths = sorted((ROOT / "validation" / "upstream").glob("*/ase-manifest.yaml"))
    assert manifest_paths
    for path in manifest_paths:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        case = data["cases"][0]
        assert case["adapter_events"] == "events.generated.jsonl"
        assert case["scenario"] == "ase-scenario.yaml"
