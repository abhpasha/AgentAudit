import json
from datetime import datetime, timedelta, timezone

import pytest

from agentaudit import LatencyEvaluator, Scenario, Trace, TraceStep

START = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


def make_trace(
    *steps: TraceStep,
    duration_ms: float = 100.0,
) -> Trace:
    return Trace(
        scenario_name="scenario",
        steps=list(steps),
        started_at=START,
        finished_at=START + timedelta(milliseconds=duration_ms),
    )


def test_no_latency_policy_is_noop() -> None:
    result = LatencyEvaluator().evaluate(
        Scenario("scenario", "prompt"),
        make_trace(),
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.summary == "No latency budget configured."


def test_total_latency_within_budget_passes() -> None:
    result = LatencyEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            max_total_latency_ms=150.0,
        ),
        make_trace(duration_ms=100.0),
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.metadata["checks_total"] == 1


def test_total_latency_over_budget_fails() -> None:
    result = LatencyEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            max_total_latency_ms=50.0,
        ),
        make_trace(duration_ms=100.0),
    )

    assert result.passed is False
    assert result.score == 0.0
    assert "Total latency exceeded budget" in result.findings[0]


def test_step_latency_budget_detects_overage() -> None:
    trace = make_trace(
        TraceStep(
            START + timedelta(milliseconds=10),
            "agent",
            "thinking",
            latency_ms=20.0,
        ),
        TraceStep(
            START + timedelta(milliseconds=30),
            "agent",
            "tool_call",
            tool_name="lookup",
            latency_ms=90.0,
        ),
    )

    result = LatencyEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            max_step_latency_ms=50.0,
        ),
        trace,
    )

    assert result.passed is False
    assert result.score == pytest.approx(0.5)
    assert "Step latency budget exceeded" in result.findings[0]


def test_missing_step_latency_is_observability_failure() -> None:
    trace = make_trace(
        TraceStep(
            START + timedelta(milliseconds=10),
            "agent",
            "thinking",
        )
    )

    result = LatencyEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            max_step_latency_ms=50.0,
        ),
        trace,
    )

    assert result.passed is False
    assert result.score == 0.0
    assert "Missing latency_ms" in result.findings[0]
    assert result.metadata["missing_step_latency"] == [1]


def test_tool_specific_latency_within_budget_passes() -> None:
    trace = make_trace(
        TraceStep(
            START + timedelta(milliseconds=10),
            "agent",
            "tool_call",
            tool_name="inventory_lookup",
            latency_ms=40.0,
        )
    )

    result = LatencyEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            tool_latency_limits_ms={"inventory_lookup": 50.0},
        ),
        trace,
    )

    assert result.passed is True
    assert result.score == 1.0


def test_tool_specific_latency_over_budget_fails() -> None:
    trace = make_trace(
        TraceStep(
            START + timedelta(milliseconds=10),
            "agent",
            "tool_call",
            tool_name="inventory_lookup",
            latency_ms=75.0,
        )
    )

    result = LatencyEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            tool_latency_limits_ms={"inventory_lookup": 50.0},
        ),
        trace,
    )

    assert result.passed is False
    assert result.score == 0.0
    assert "Tool latency budget exceeded" in result.findings[0]


def test_missing_tool_latency_is_observability_failure() -> None:
    trace = make_trace(
        TraceStep(
            START + timedelta(milliseconds=10),
            "agent",
            "tool_call",
            tool_name="inventory_lookup",
        )
    )

    result = LatencyEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            tool_latency_limits_ms={"inventory_lookup": 50.0},
        ),
        trace,
    )

    assert result.passed is False
    assert result.score == 0.0
    assert "Missing latency_ms for tool calls" in result.findings[0]


def test_unconfigured_tool_does_not_create_tool_budget_check() -> None:
    trace = make_trace(
        TraceStep(
            START + timedelta(milliseconds=10),
            "agent",
            "tool_call",
            tool_name="other_tool",
        )
    )

    result = LatencyEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            tool_latency_limits_ms={"inventory_lookup": 50.0},
        ),
        trace,
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.metadata["checks_total"] == 0


def test_combined_latency_policies_have_deterministic_score() -> None:
    trace = make_trace(
        TraceStep(
            START + timedelta(milliseconds=10),
            "agent",
            "tool_call",
            tool_name="inventory_lookup",
            latency_ms=75.0,
        ),
        duration_ms=100.0,
    )

    result = LatencyEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            max_total_latency_ms=150.0,
            max_step_latency_ms=100.0,
            tool_latency_limits_ms={"inventory_lookup": 50.0},
        ),
        trace,
    )

    assert result.passed is False
    assert result.score == pytest.approx(2 / 3)
    assert result.metadata["checks_total"] == 3
    assert result.metadata["checks_passed"] == 2


def test_latency_result_is_json_serialisable() -> None:
    result = LatencyEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            max_total_latency_ms=150.0,
        ),
        make_trace(duration_ms=100.0),
    )

    decoded = json.loads(result.to_json())

    assert decoded["evaluator_name"] == "latency"
    assert decoded["metadata"]["total_latency_ms"] == 100.0
