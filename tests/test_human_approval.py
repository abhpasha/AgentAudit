from datetime import datetime, timedelta, timezone

from agentaudit import (
    HUMAN_APPROVAL_DENIED,
    HUMAN_APPROVAL_GRANTED,
    HUMAN_APPROVAL_REQUESTED,
    HumanApprovalEvaluator,
    Scenario,
    Trace,
    TraceStep,
)


def make_trace(*steps: TraceStep) -> Trace:
    start = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    return Trace(
        scenario_name="scenario",
        steps=list(steps),
        started_at=start,
        finished_at=start + timedelta(seconds=20),
    )


def test_no_approval_policy_is_noop() -> None:
    result = HumanApprovalEvaluator().evaluate(
        Scenario("scenario", "prompt"),
        make_trace(),
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.summary == "No human approval policy configured."


def test_matching_approval_before_protected_action_passes() -> None:
    start = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    trace = make_trace(
        TraceStep(
            start + timedelta(seconds=1),
            "agent",
            HUMAN_APPROVAL_REQUESTED,
            approval_id="approval-1",
        ),
        TraceStep(
            start + timedelta(seconds=2),
            "human",
            HUMAN_APPROVAL_GRANTED,
            approval_id="approval-1",
        ),
        TraceStep(
            start + timedelta(seconds=3),
            "agent",
            "tool_call",
            tool_name="payment_submit",
            approval_id="approval-1",
        ),
    )

    result = HumanApprovalEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            approval_required_before=["payment_submit"],
        ),
        trace,
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.metadata["approved_tool_calls"] == 1


def test_missing_approval_fails() -> None:
    start = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    result = HumanApprovalEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            approval_required_before=["payment_submit"],
        ),
        make_trace(
            TraceStep(
                start + timedelta(seconds=1),
                "agent",
                "tool_call",
                tool_name="payment_submit",
            )
        ),
    )

    assert result.passed is False
    assert result.score == 0.0
    assert "not preceded by valid human approval" in result.findings[0]


def test_late_approval_fails() -> None:
    start = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    trace = make_trace(
        TraceStep(
            start + timedelta(seconds=1),
            "agent",
            "tool_call",
            tool_name="payment_submit",
        ),
        TraceStep(
            start + timedelta(seconds=2),
            "agent",
            HUMAN_APPROVAL_REQUESTED,
            approval_id="approval-1",
        ),
        TraceStep(
            start + timedelta(seconds=3),
            "human",
            HUMAN_APPROVAL_GRANTED,
            approval_id="approval-1",
        ),
    )

    result = HumanApprovalEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            approval_required_before=["payment_submit"],
        ),
        trace,
    )

    assert result.passed is False
    assert result.score == 0.0


def test_denial_followed_by_protected_action_fails() -> None:
    start = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    trace = make_trace(
        TraceStep(
            start + timedelta(seconds=1),
            "agent",
            HUMAN_APPROVAL_REQUESTED,
            approval_id="approval-1",
        ),
        TraceStep(
            start + timedelta(seconds=2),
            "human",
            HUMAN_APPROVAL_GRANTED,
            approval_id="approval-1",
        ),
        TraceStep(
            start + timedelta(seconds=3),
            "human",
            HUMAN_APPROVAL_DENIED,
            approval_id="approval-1",
        ),
        TraceStep(
            start + timedelta(seconds=4),
            "agent",
            "tool_call",
            tool_name="payment_submit",
            approval_id="approval-1",
        ),
    )

    result = HumanApprovalEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            approval_required_before=["payment_submit"],
        ),
        trace,
    )

    assert result.passed is False
    assert result.score == 0.0


def test_mismatched_approval_ids_fail() -> None:
    start = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    trace = make_trace(
        TraceStep(
            start + timedelta(seconds=1),
            "agent",
            HUMAN_APPROVAL_REQUESTED,
            approval_id="approval-a",
        ),
        TraceStep(
            start + timedelta(seconds=2),
            "human",
            HUMAN_APPROVAL_GRANTED,
            approval_id="approval-b",
        ),
        TraceStep(
            start + timedelta(seconds=3),
            "agent",
            "tool_call",
            tool_name="payment_submit",
            approval_id="approval-a",
        ),
    )

    result = HumanApprovalEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            approval_required_before=["payment_submit"],
        ),
        trace,
    )

    assert result.passed is False
    assert any("without a matching earlier request" in item for item in result.findings)
    assert any("approval-a" in item for item in result.findings)


def test_requires_human_approval_protects_all_tool_calls_without_explicit_list() -> None:
    start = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    trace = make_trace(
        TraceStep(
            start + timedelta(seconds=1),
            "agent",
            HUMAN_APPROVAL_REQUESTED,
            approval_id="approval-1",
        ),
        TraceStep(
            start + timedelta(seconds=2),
            "human",
            HUMAN_APPROVAL_GRANTED,
            approval_id="approval-1",
        ),
        TraceStep(
            start + timedelta(seconds=3),
            "agent",
            "tool_call",
            tool_name="inventory_update",
        ),
        TraceStep(
            start + timedelta(seconds=4),
            "agent",
            "tool_call",
            tool_name="audit_log_write",
        ),
    )

    result = HumanApprovalEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            requires_human_approval=True,
        ),
        trace,
    )

    assert result.passed is True
    assert result.metadata["protected_tool_calls"] == 2
    assert result.metadata["approved_tool_calls"] == 2


def test_requires_human_approval_without_tool_calls_requires_valid_pair() -> None:
    result = HumanApprovalEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            requires_human_approval=True,
        ),
        make_trace(),
    )

    assert result.passed is False
    assert result.score == 0.0
    assert "no valid matching request/grant pair" in result.findings[0]


def test_unprotected_tool_does_not_require_approval() -> None:
    start = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
    result = HumanApprovalEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            approval_required_before=["payment_submit"],
        ),
        make_trace(
            TraceStep(
                start + timedelta(seconds=1),
                "agent",
                "tool_call",
                tool_name="inventory_lookup",
            )
        ),
    )

    assert result.passed is True
    assert result.metadata["protected_tool_calls"] == 0
