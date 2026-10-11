import json
from datetime import datetime, timezone

import pytest

from agentaudit import (
    EvaluationSuite,
    Scenario,
    Trace,
    TraceStep,
    evaluate_suite,
    run_evaluation,
)


class LookupAgent:
    def run(self, scenario: Scenario) -> Trace:
        now = datetime.now(timezone.utc)
        return Trace(
            scenario_name=scenario.name,
            steps=[
                TraceStep(
                    timestamp=now,
                    actor="agent",
                    action_type="tool_call",
                    tool_name="lookup",
                    latency_ms=1.0,
                )
            ],
            started_at=now,
            finished_at=now,
        )


def test_run_evaluation_uses_full_v02_default_evaluator_set() -> None:
    result = run_evaluation(
        LookupAgent(),
        Scenario("scenario", "prompt", expected_tools=["lookup"]),
    )

    assert [item.evaluator_name for item in result.results] == [
        "trace_integrity",
        "tool_selection",
        "tool_sequence",
        "human_approval",
        "latency",
        "execution_failure",
        "evidence_grounding",
    ]
    assert result.passed is True
    assert result.score == 1.0
    assert result.metadata["evaluator_count"] == 7


def test_evaluation_suite_rejects_empty_suite() -> None:
    with pytest.raises(ValueError, match="at least one scenario"):
        EvaluationSuite("empty", [])


def test_evaluation_suite_rejects_duplicate_scenario_names() -> None:
    with pytest.raises(ValueError, match="scenario names must be unique"):
        EvaluationSuite(
            "duplicates",
            [
                Scenario("same", "first"),
                Scenario("same", "second"),
            ],
        )


def test_all_pass_suite_aggregates_successfully() -> None:
    suite = EvaluationSuite(
        "smoke",
        [
            Scenario("first", "prompt", expected_tools=["lookup"]),
            Scenario("second", "prompt", expected_tools=["lookup"]),
        ],
    )

    result = evaluate_suite(LookupAgent(), suite)

    assert result.passed is True
    assert result.score == 1.0
    assert result.total_scenarios == 2
    assert result.passed_scenarios == 2
    assert result.failed_scenarios == 0
    assert result.pass_rate == 1.0


def test_partial_failure_has_deterministic_aggregate_score() -> None:
    suite = EvaluationSuite(
        "regression",
        [
            Scenario("passing", "prompt", expected_tools=["lookup"]),
            Scenario("failing", "prompt", expected_tools=["other"]),
        ],
    )

    result = evaluate_suite(LookupAgent(), suite)

    assert result.passed is False
    assert result.scenario_results[0].score == 1.0
    assert result.scenario_results[1].score == pytest.approx(6 / 7)
    assert result.score == pytest.approx(13 / 14)
    assert result.passed_scenarios == 1
    assert result.failed_scenarios == 1
    assert result.pass_rate == pytest.approx(0.5)


def test_suite_and_result_are_json_serialisable() -> None:
    suite = EvaluationSuite(
        "serialisation",
        [Scenario("scenario", "prompt", expected_tools=["lookup"])],
        metadata={"kind": "smoke"},
    )
    suite_payload = json.loads(suite.to_json())

    result = evaluate_suite(LookupAgent(), suite)
    result_payload = json.loads(result.to_json())

    assert suite_payload["name"] == "serialisation"
    assert suite_payload["metadata"] == {"kind": "smoke"}
    assert result_payload["suite_name"] == "serialisation"
    assert result_payload["scenario_results"][0]["scenario_name"] == "scenario"


def test_custom_empty_evaluator_sequence_is_deterministic() -> None:
    result = run_evaluation(
        LookupAgent(),
        Scenario("scenario", "prompt"),
        evaluators=[],
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.results == []
