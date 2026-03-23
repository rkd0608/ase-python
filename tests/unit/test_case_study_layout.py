from __future__ import annotations

from pathlib import Path


def test_case_study_docs_exist() -> None:
    root = Path(__file__).resolve().parents[2]
    docs = root / "docs" / "case-studies"
    assert (docs / "README.md").exists()
    assert (docs / "openai-prompt-regression.md").exists()
    assert (docs / "pydantic-approval-gate.md").exists()
    assert (docs / "langgraph-wrong-record.md").exists()


def test_case_study_scenarios_exist() -> None:
    root = Path(__file__).resolve().parents[2]
    studies = root / "validation" / "case_studies"
    assert (studies / "openai_prompt_regression" / "scenario.bad.yaml").exists()
    assert (studies / "openai_prompt_regression" / "scenario.fixed.yaml").exists()
    assert (studies / "pydantic_missing_approval" / "scenario.bad.yaml").exists()
    assert (studies / "pydantic_missing_approval" / "scenario.fixed.yaml").exists()
    assert (studies / "langgraph_wrong_record" / "scenario.bad.yaml").exists()
    assert (studies / "langgraph_wrong_record" / "scenario.fixed.yaml").exists()
