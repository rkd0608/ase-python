"""Shared evaluator protocol and result models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Pillar(StrEnum):
    """Define ASE's top-level scoring buckets."""

    CORRECTNESS = "correctness"
    SAFETY = "safety"
    EFFICIENCY = "efficiency"
    CONSISTENCY = "consistency"
    CUSTOM = "custom"


class AssertionResult(BaseModel):
    """Represent one evaluator outcome within a scenario run."""

    evaluator: str
    pillar: Pillar
    passed: bool
    score: float
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class EvaluationSummary(BaseModel):
    """Summarize all evaluator outcomes for one trace."""

    trace_id: str
    scenario_id: str
    passed: bool
    ase_score: float
    total: int
    passed_count: int
    failed_count: int
    results: list[AssertionResult] = Field(default_factory=list)
    pillar_scores: dict[str, float] = Field(default_factory=dict)
    failing_evaluators: list[str] = Field(default_factory=list)


class Evaluator(ABC):
    """Define the stable extension point for ASE assertions."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the public evaluator name referenced by scenarios."""

    @property
    @abstractmethod
    def pillar(self) -> Pillar:
        """Return the default scoring pillar for this evaluator."""

    @abstractmethod
    def evaluate(self, trace: object, params: dict[str, Any], **context: Any) -> AssertionResult:
        """Evaluate one trace and return a structured assertion result."""
