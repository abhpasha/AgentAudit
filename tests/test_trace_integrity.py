from datetime import datetime, timedelta, timezone

from agentaudit import Evidence, Scenario, Trace, TraceIntegrityEvaluator, TraceStep


def make_trace(*steps: TraceStep, evidence: list[Evidence] | None = None) -> Trace:
    start = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    return Trace(
        scenario_name="scenario",
        steps=list(steps),
        started_at=start,
        finished_at=start + timedelta(seconds=10),
        evidence=evidence or [],
    )


def test_trace_integrity_passes_valid_trace() -> None:
    start = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    evidence = Evidence("ev-1", "inventory_database", {"quantity": 4})
    trace = make_trace(
        TraceStep(
            start + timedelta(seconds=1),
            "agent",
            "human_approval_requested",
            approval_id="approval-1",
        ),
        TraceStep(
            start + timedelta(seconds=2),
            "human",
            "human_approval_granted",
            approval_id="approval-1",
        ),
        TraceStep(
            start + timedelta(seconds=3),
            "agent",
            "tool_call",
            tool_name="inventory_lookup",
            evidence_ids=["ev-1"],
            attempt=1,
        ),
        evidence=[evidence],
    )

    result = TraceIntegrityEvaluator().evaluate(
        Scenario("scenario", "prompt"),
        trace,
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.findings == []


def test_trace_integrity_detects_scenario_mismatch() -> None:
    result = TraceIntegrityEvaluator().evaluate(
        Scenario("expected", "prompt"),
        make_trace(),
    )

    assert result.passed is False
    assert any("scenario_name" in finding for finding in result.findings)


def test_trace_integrity_detects_duplicate_and_broken_evidence() -> None:
    start = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    trace = make_trace(
        TraceStep(
            start + timedelta(seconds=1),
            "agent",
            "final_output",
            evidence_ids=["missing"],
        ),
        evidence=[
            Evidence("duplicate", "source-a"),
            Evidence("duplicate", "source-b"),
        ],
    )

    result = TraceIntegrityEvaluator().evaluate(
        Scenario("scenario", "prompt"),
        trace,
    )

    assert result.passed is False
    assert "Duplicate evidence IDs: duplicate" in result.findings
    assert "Unresolved evidence references: missing" in result.findings


def test_trace_integrity_detects_out_of_order_and_out_of_bounds_steps() -> None:
    start = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    trace = make_trace(
        TraceStep(start + timedelta(seconds=3), "agent", "thinking"),
        TraceStep(start + timedelta(seconds=2), "agent", "thinking"),
        TraceStep(start + timedelta(seconds=11), "agent", "thinking"),
    )

    result = TraceIntegrityEvaluator().evaluate(
        Scenario("scenario", "prompt"),
        trace,
    )

    assert result.passed is False
    assert "Trace step timestamps are not non-decreasing" in result.findings
    assert "Trace steps outside trace time bounds: 3" in result.findings


def test_trace_integrity_detects_tool_call_without_name() -> None:
    start = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    result = TraceIntegrityEvaluator().evaluate(
        Scenario("scenario", "prompt"),
        make_trace(TraceStep(start, "agent", "tool_call")),
    )

    assert result.passed is False
    assert "tool_call steps missing tool_name: 1" in result.findings


def test_trace_integrity_detects_approval_event_without_id() -> None:
    start = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    result = TraceIntegrityEvaluator().evaluate(
        Scenario("scenario", "prompt"),
        make_trace(TraceStep(start, "agent", "human_approval_requested")),
    )

    assert result.passed is False
    assert "Approval steps missing approval_id: 1" in result.findings


def test_trace_integrity_detects_invalid_retry_attempt() -> None:
    start = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    result = TraceIntegrityEvaluator().evaluate(
        Scenario("scenario", "prompt"),
        make_trace(
            TraceStep(
                start,
                "agent",
                "tool_call",
                tool_name="lookup",
                attempt=0,
            )
        ),
    )

    assert result.passed is False
    assert "Trace steps with attempt < 1: 1" in result.findings


def test_trace_integrity_detects_error_type_without_error() -> None:
    start = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    result = TraceIntegrityEvaluator().evaluate(
        Scenario("scenario", "prompt"),
        make_trace(
            TraceStep(
                start,
                "agent",
                "tool_call",
                tool_name="lookup",
                error_type="TimeoutError",
            )
        ),
    )

    assert result.passed is False
    assert "Trace steps with error_type but no error: 1" in result.findings
