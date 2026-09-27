"""Public high-level API."""

from __future__ import annotations

from collections.abc import Sequence

from .evaluators import Evaluator, ToolSelectionEvaluator, ToolSequenceEvaluator
from .models import EvaluationResult, Scenario
from .runner import Agent, BasicRunner, Runner

_DEFAULT_EVALUATORS: tuple[Evaluator, ...] = (
    ToolSelectionEvaluator(),
    ToolSequenceEvaluator(),
)


def evaluate(
    agent: Agent,
    scenario: Scenario,
    *,
    runner: Runner | None = None,
    evaluators: Sequence[Evaluator] | None = None,
) -> list[EvaluationResult]:
    """Run an agent once and evaluate its trace deterministically.

    The function returns one ``EvaluationResult`` per evaluator. By default,
    AgentAudit runs tool-selection and tool-sequence checks.
    """
    active_runner = runner or BasicRunner()
    trace = active_runner.run(agent, scenario)
    active_evaluators = tuple(evaluators) if evaluators is not None else _DEFAULT_EVALUATORS
    return [evaluator.evaluate(scenario, trace) for evaluator in active_evaluators]
