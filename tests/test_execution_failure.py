from datetime import datetime, timedelta, timezone

import pytest

from agentaudit import ExecutionFailureEvaluator, Scenario, Trace, TraceStep

START = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)


def make_trace(*steps: TraceStep) -> Trace:
    return Trace(
        scenario_name="scenario",
        steps=list(steps),
        started_at=START,
        finished_at=START + timedelta(seconds=1),
    )


def tool_step(
    offset_ms: int,
    *,
    tool: str = "lookup",
    error: str | None = None,
    error_type: str | None = None,
    retryable: bool | None = None,
    attempt: int | None = None,
) -> TraceStep:
    return TraceStep(
        START + timedelta(milliseconds=offset_ms),
        "agent",
        "tool_call",
        tool_name=tool,
        error=error,
        error_type=error_type,
        retryable=retryable,
        attempt=attempt,
    )


def test_no_error_run_passes_default_policy() -> None:
    result = ExecutionFailureEvaluator().evaluate(
        Scenario("scenario", "prompt"),
        make_trace(tool_step(10)),
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.metadata["error_count"] == 0


def test_error_count_over_default_zero_fails() -> None:
    result = ExecutionFailureEvaluator().evaluate(
        Scenario("scenario", "prompt"),
        make_trace(
            tool_step(
                10,
                error="timeout",
                error_type="TimeoutError",
                retryable=True,
            )
        ),
    )

    assert result.passed is False
    assert "Error count exceeded policy" in result.findings[0]


def test_allowed_error_type_within_error_budget_passes() -> None:
    result = ExecutionFailureEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            max_errors=1,
            allowed_error_types=["TimeoutError"],
        ),
        make_trace(
            tool_step(
                10,
                error="timeout",
                error_type="TimeoutError",
                retryable=False,
            )
        ),
    )

    assert result.passed is True


def test_unexpected_error_type_fails() -> None:
    result = ExecutionFailureEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            max_errors=1,
            allowed_error_types=["TimeoutError"],
        ),
        make_trace(
            tool_step(
                10,
                error="permission denied",
                error_type="PermissionError",
                retryable=False,
            )
        ),
    )

    assert result.passed is False
    assert "Unexpected error types" in result.findings[0]


def test_successful_retry_passes() -> None:
    trace = make_trace(
        tool_step(
            10,
            error="timeout",
            error_type="TimeoutError",
            retryable=True,
            attempt=1,
        ),
        tool_step(20, attempt=2),
    )

    result = ExecutionFailureEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            max_errors=1,
            allowed_error_types=["TimeoutError"],
            max_retries_per_tool=1,
        ),
        trace,
    )

    assert result.passed is True
    assert result.metadata["retries_by_tool"] == {"lookup": 1}


@pytest.mark.parametrize("attempt", [0, 2, 3])
def test_malformed_first_attempt_fails(attempt: int) -> None:
    result = ExecutionFailureEvaluator().evaluate(
        Scenario("scenario", "prompt", max_retries_per_tool=3),
        make_trace(tool_step(10, attempt=attempt)),
    )

    assert result.passed is False
    assert "Malformed retry attempts" in result.findings[0]


def test_attempt_gap_is_malformed() -> None:
    trace = make_trace(
        tool_step(
            10,
            error="timeout",
            error_type="TimeoutError",
            retryable=True,
            attempt=1,
        ),
        tool_step(20, attempt=3),
    )

    result = ExecutionFailureEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            max_errors=1,
            max_retries_per_tool=3,
        ),
        trace,
    )

    assert result.passed is False
    assert "Malformed retry attempts" in result.findings[0]


def test_retry_after_non_retryable_error_fails() -> None:
    trace = make_trace(
        tool_step(
            10,
            error="bad request",
            error_type="ValidationError",
            retryable=False,
            attempt=1,
        ),
        tool_step(20, attempt=2),
    )

    result = ExecutionFailureEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            max_errors=1,
            max_retries_per_tool=1,
        ),
        trace,
    )

    assert result.passed is False
    assert "Retry attempted without a retryable preceding error" in result.findings[0]


def test_retry_after_success_fails() -> None:
    trace = make_trace(
        tool_step(10, attempt=1),
        tool_step(20, attempt=2),
    )

    result = ExecutionFailureEvaluator().evaluate(
        Scenario("scenario", "prompt", max_retries_per_tool=1),
        trace,
    )

    assert result.passed is False
    assert "Retry attempted without a retryable preceding error" in result.findings[0]


def test_retry_limit_violation_fails() -> None:
    trace = make_trace(
        tool_step(
            10,
            error="timeout",
            error_type="TimeoutError",
            retryable=True,
            attempt=1,
        ),
        tool_step(
            20,
            error="timeout",
            error_type="TimeoutError",
            retryable=True,
            attempt=2,
        ),
        tool_step(30, attempt=3),
    )

    result = ExecutionFailureEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            max_errors=2,
            allowed_error_types=["TimeoutError"],
            max_retries_per_tool=1,
        ),
        trace,
    )

    assert result.passed is False
    assert result.metadata["retries_by_tool"] == {"lookup": 2}
    assert "Retry limit exceeded" in result.findings[0]


def test_duplicate_tool_calls_without_attempt_metadata_are_not_retries() -> None:
    trace = make_trace(
        tool_step(10),
        tool_step(20),
        tool_step(30),
    )

    result = ExecutionFailureEvaluator().evaluate(
        Scenario("scenario", "prompt", max_retries_per_tool=0),
        trace,
    )

    assert result.passed is True
    assert result.metadata["retries_by_tool"] == {"lookup": 0}


def test_retry_counts_are_independent_per_tool() -> None:
    trace = make_trace(
        tool_step(
            10,
            tool="lookup",
            error="timeout",
            error_type="TimeoutError",
            retryable=True,
            attempt=1,
        ),
        tool_step(20, tool="lookup", attempt=2),
        tool_step(
            30,
            tool="search",
            error="timeout",
            error_type="TimeoutError",
            retryable=True,
            attempt=1,
        ),
        tool_step(40, tool="search", attempt=2),
    )

    result = ExecutionFailureEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            max_errors=2,
            allowed_error_types=["TimeoutError"],
            max_retries_per_tool=1,
        ),
        trace,
    )

    assert result.passed is True
    assert result.metadata["retries_by_tool"] == {"lookup": 1, "search": 1}


def test_untyped_error_is_unexpected_when_allowlist_is_configured() -> None:
    result = ExecutionFailureEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            max_errors=1,
            allowed_error_types=["TimeoutError"],
        ),
        make_trace(tool_step(10, error="unknown")),
    )

    assert result.passed is False
    assert result.metadata["unexpected_errors"] == [
        {"step": 1, "error_type": None}
    ]
