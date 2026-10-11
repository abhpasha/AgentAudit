"""Public high-level evaluation API."""

from __future__ import annotations

from collections.abc import Sequence

from .evaluators import (
    Evaluator,
    EvidenceGroundingEvaluator,
    ExecutionFailureEvaluator,
    HumanApprovalEvaluator,
    LatencyEvaluator,
    ToolSelectionEvaluator,
    ToolSequenceEvaluator,
    TraceIntegrityEvaluator,
)
from .models import (
    EvaluationResult,
    EvaluationSuite,
    JSONValue,
    Scenario,
    ScenarioEvaluation,
    SuiteResult,
)
from .runner import Agent, BasicRunner, Runner

_LEGACY_DEFAULT_EVALUATORS: tuple[Evaluator, ...] = (
    ToolSelectionEvaluator(),
    ToolSequenceEvaluator(),
)

_DEFAULT_EVALUATORS: tuple[Evaluator, ...] = (
    TraceIntegrityEvaluator(),
    ToolSelectionEvaluator(),
    ToolSequenceEvaluator(),
    HumanApprovalEvaluator(),
    LatencyEvaluator(),
    ExecutionFailureEvaluator(),
    EvidenceGroundingEvaluator(),
)


def run_evaluation(
    agent: Agent,
    scenario: Scenario,
    *,
    runner: Runner | None = None,
    evaluators: Sequence[Evaluator] | None = None,
) -> ScenarioEvaluation:
    """Run one scenario and return its trace plus deterministic evaluations."""

    active_runner = runner or BasicRunner()
    trace = active_runner.run(agent, scenario)
    active_evaluators = (
        tuple(evaluators) if evaluators is not None else _DEFAULT_EVALUATORS
    )
    results = [
        evaluator.evaluate(scenario, trace)
        for evaluator in active_evaluators
    ]
    passed = all(result.passed for result in results)
    score = (
        sum(result.score for result in results) / len(results)
        if results
        else 1.0
    )
    metadata: dict[str, JSONValue] = {
        "evaluator_count": len(results),
        "passed_evaluators": sum(int(result.passed) for result in results),
        "failed_evaluators": sum(int(not result.passed) for result in results),
    }
    return ScenarioEvaluation(
        scenario_name=scenario.name,
        trace=trace,
        results=results,
        passed=passed,
        score=score,
        metadata=metadata,
    )


def evaluate_suite(
    agent: Agent,
    suite: EvaluationSuite,
    *,
    runner: Runner | None = None,
    evaluators: Sequence[Evaluator] | None = None,
) -> SuiteResult:
    """Run every scenario in a suite and aggregate deterministic results."""

    active_runner = runner or BasicRunner()
    active_evaluators = (
        tuple(evaluators) if evaluators is not None else _DEFAULT_EVALUATORS
    )
    scenario_results = [
        run_evaluation(
            agent,
            scenario,
            runner=active_runner,
            evaluators=active_evaluators,
        )
        for scenario in suite.scenarios
    ]

    passed = all(result.passed for result in scenario_results)
    score = sum(result.score for result in scenario_results) / len(scenario_results)
    passed_count = sum(int(result.passed) for result in scenario_results)
    metadata: dict[str, JSONValue] = {
        "scenario_count": len(scenario_results),
        "passed_scenarios": passed_count,
        "failed_scenarios": len(scenario_results) - passed_count,
    }
    return SuiteResult(
        suite_name=suite.name,
        scenario_results=scenario_results,
        passed=passed,
        score=score,
        metadata=metadata,
    )


def evaluate(
    agent: Agent,
    scenario: Scenario,
    *,
    runner: Runner | None = None,
    evaluators: Sequence[Evaluator] | None = None,
) -> list[EvaluationResult]:
    """Run one scenario and return evaluator results.

    Omitting evaluators retains the v0.1 tool-selection and tool-sequence
    defaults. Use run_evaluation for the full v0.2 governance evaluator set.
    """

    active_evaluators = (
        tuple(evaluators)
        if evaluators is not None
        else _LEGACY_DEFAULT_EVALUATORS
    )
    return run_evaluation(
        agent,
        scenario,
        runner=runner,
        evaluators=active_evaluators,
    ).results
