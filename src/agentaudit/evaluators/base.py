"""Evaluator interface."""

from __future__ import annotations

from typing import Protocol

from agentaudit.models import EvaluationResult, Scenario, Trace


class Evaluator(Protocol):
    """Protocol implemented by all deterministic and future evaluators."""

    @property
    def name(self) -> str:
        """Stable evaluator identifier."""
        ...

    def evaluate(self, scenario: Scenario, trace: Trace) -> EvaluationResult:
        """Evaluate one trace against one scenario."""
        ...
