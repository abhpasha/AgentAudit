from datetime import datetime, timedelta, timezone

import pytest

from agentaudit import EvaluationResult, Scenario, Trace, TraceStep


def test_scenario_accepts_valid_configuration() -> None:
    scenario = Scenario(
        name="stock_check",
        prompt="Check stock",
        expected_tools=["inventory_lookup"],
        forbidden_tools=["customer_database"],
        max_tool_calls=2,
        metadata={"suite": "smoke"},
    )
    assert scenario.name == "stock_check"


@pytest.mark.parametrize("field", ["name", "prompt"])
def test_scenario_rejects_blank_required_fields(field: str) -> None:
    kwargs = {"name": "scenario", "prompt": "prompt"}
    kwargs[field] = "   "
    with pytest.raises(ValueError):
        Scenario(**kwargs)


def test_scenario_rejects_tool_overlap() -> None:
    with pytest.raises(ValueError, match="both expected and forbidden"):
        Scenario(
            name="invalid",
            prompt="prompt",
            expected_tools=["lookup"],
            forbidden_tools=["lookup"],
        )


def test_scenario_rejects_negative_max_tool_calls() -> None:
    with pytest.raises(ValueError, match="max_tool_calls"):
        Scenario(name="invalid", prompt="prompt", max_tool_calls=-1)


def test_scenario_rejects_non_json_metadata() -> None:
    with pytest.raises(TypeError, match="JSON-serialisable"):
        Scenario(
            name="invalid",
            prompt="prompt",
            metadata={"bad": {1, 2}},  # type: ignore[dict-item]
        )


def test_trace_json_round_trip() -> None:
    started_at = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    trace = Trace(
        scenario_name="stock_check",
        steps=[
            TraceStep(
                timestamp=started_at + timedelta(milliseconds=5),
                actor="agent",
                action_type="tool_call",
                tool_name="inventory_lookup",
                input={"sku": "ABC123"},
                output={"quantity": 4},
                latency_ms=5.0,
                metadata={"attempt": 1},
            )
        ],
        started_at=started_at,
        finished_at=started_at + timedelta(milliseconds=10),
        metadata={"run_id": "run-1"},
    )

    restored = Trace.from_json(trace.to_json())
    assert restored == trace
    assert restored.tool_names == ["inventory_lookup"]


def test_trace_rejects_naive_datetimes() -> None:
    now = datetime(2026, 9, 27, 12, 0)
    with pytest.raises(ValueError, match="timezone-aware"):
        Trace("scenario", [], now, now)


def test_evaluation_result_validates_score() -> None:
    with pytest.raises(ValueError, match="score"):
        EvaluationResult("test", 1.1, True, "invalid")
