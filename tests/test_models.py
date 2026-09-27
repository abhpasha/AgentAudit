from datetime import datetime, timedelta, timezone

import pytest

from agentaudit import EvaluationResult, Evidence, Scenario, Trace, TraceStep


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


def test_scenario_rejects_evidence_source_overlap() -> None:
    with pytest.raises(ValueError, match="both required and forbidden"):
        Scenario(
            name="invalid",
            prompt="prompt",
            required_evidence_sources=["inventory"],
            forbidden_evidence_sources=["inventory"],
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_tool_calls", -1),
        ("max_errors", -1),
        ("max_retries_per_tool", -1),
        ("min_evidence_items", -1),
        ("max_total_latency_ms", -0.1),
        ("max_step_latency_ms", float("inf")),
    ],
)
def test_scenario_rejects_invalid_nonnegative_policy_values(
    field: str,
    value: int | float,
) -> None:
    kwargs: dict[str, object] = {"name": "invalid", "prompt": "prompt", field: value}
    with pytest.raises(ValueError):
        Scenario(**kwargs)  # type: ignore[arg-type]


def test_scenario_rejects_invalid_tool_latency_limit() -> None:
    with pytest.raises(ValueError, match="tool_latency_limits_ms"):
        Scenario(
            name="invalid",
            prompt="prompt",
            tool_latency_limits_ms={"lookup": -1.0},
        )


def test_scenario_rejects_non_json_metadata() -> None:
    with pytest.raises(TypeError, match="JSON-serialisable"):
        Scenario(
            name="invalid",
            prompt="prompt",
            metadata={"bad": {1, 2}},  # type: ignore[dict-item]
        )


def test_scenario_v02_json_round_trip() -> None:
    scenario = Scenario(
        name="governed_stock_check",
        prompt="Check and update stock",
        expected_tools=["lookup"],
        forbidden_tools=["customer_database"],
        expected_tool_sequence=["lookup", "update"],
        max_tool_calls=3,
        requires_human_approval=True,
        metadata={"owner": "inventory"},
        approval_required_before=["update"],
        max_total_latency_ms=2_000.0,
        max_step_latency_ms=800.0,
        tool_latency_limits_ms={"lookup": 500.0},
        max_errors=1,
        allowed_error_types=["TimeoutError"],
        max_retries_per_tool=2,
        required_evidence_sources=["inventory_database"],
        forbidden_evidence_sources=["customer_database"],
        min_evidence_items=1,
        require_evidence_on_final_output=True,
    )

    restored = Scenario.from_json(scenario.to_json())

    assert restored == scenario


def test_evidence_validates_and_serialises() -> None:
    retrieved_at = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    evidence = Evidence(
        id="ev-1",
        source="inventory_database",
        content={"sku": "ABC123", "quantity": 4},
        uri="inventory://ABC123",
        content_hash="sha256:abc",
        retrieved_at=retrieved_at,
        metadata={"region": "uk"},
    )

    restored = Evidence.from_dict(evidence.to_dict())

    assert restored == evidence


@pytest.mark.parametrize(
    "kwargs",
    [
        {"id": "", "source": "source"},
        {"id": "ev-1", "source": ""},
        {"id": "ev-1", "source": "source", "uri": " "},
        {"id": "ev-1", "source": "source", "content_hash": " "},
    ],
)
def test_evidence_rejects_blank_identifiers(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        Evidence(**kwargs)  # type: ignore[arg-type]


def test_evidence_rejects_naive_retrieval_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Evidence(
            id="ev-1",
            source="source",
            retrieved_at=datetime(2026, 9, 27, 12, 0),
        )


def test_trace_json_round_trip_includes_v02_fields_and_evidence() -> None:
    started_at = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    evidence = Evidence(
        id="ev-1",
        source="inventory_database",
        content={"sku": "ABC123", "quantity": 4},
        retrieved_at=started_at,
    )
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
                error="temporary timeout",
                metadata={"request_id": "req-1"},
                evidence_ids=["ev-1"],
                approval_id="approval-1",
                error_type="TimeoutError",
                retryable=True,
                attempt=1,
            ),
            TraceStep(
                timestamp=started_at + timedelta(milliseconds=8),
                actor="agent",
                action_type="final_output",
                output={"in_stock": True},
                evidence_ids=["ev-1"],
            ),
        ],
        started_at=started_at,
        finished_at=started_at + timedelta(milliseconds=10),
        metadata={"run_id": "run-1"},
        evidence=[evidence],
    )

    restored = Trace.from_json(trace.to_json())

    assert restored == trace
    assert restored.tool_names == ["inventory_lookup"]
    assert restored.error_steps == [restored.steps[0]]
    assert restored.total_latency_ms == pytest.approx(10.0)
    assert restored.evidence_by_id == {"ev-1": restored.evidence[0]}
    assert restored.final_output_steps == [restored.steps[1]]


def test_trace_step_rejects_duplicate_evidence_references() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="evidence_ids"):
        TraceStep(
            now,
            "agent",
            "final_output",
            evidence_ids=["ev-1", "ev-1"],
        )


def test_trace_step_rejects_negative_or_nonfinite_latency() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="latency_ms"):
        TraceStep(now, "agent", "tool_call", latency_ms=float("nan"))


def test_trace_rejects_naive_datetimes() -> None:
    now = datetime(2026, 9, 27, 12, 0)
    with pytest.raises(ValueError, match="timezone-aware"):
        Trace("scenario", [], now, now)


def test_trace_rejects_finished_before_started() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="finished_at"):
        Trace("scenario", [], now, now - timedelta(seconds=1))


def test_scenario_and_trace_json_require_objects() -> None:
    with pytest.raises(TypeError, match="Scenario JSON"):
        Scenario.from_json("[]")
    with pytest.raises(TypeError, match="Trace JSON"):
        Trace.from_json("[]")


def test_evaluation_result_validates_score() -> None:
    with pytest.raises(ValueError, match="score"):
        EvaluationResult("test", 1.1, True, "invalid")
