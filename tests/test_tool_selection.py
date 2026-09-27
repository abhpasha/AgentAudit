from datetime import datetime, timezone

from agentaudit import Scenario, Trace, TraceStep
from agentaudit.evaluators import ToolSelectionEvaluator


def make_trace(*tools: str) -> Trace:
    now = datetime.now(timezone.utc)
    return Trace(
        scenario_name="scenario",
        steps=[
            TraceStep(
                timestamp=now,
                actor="agent",
                action_type="tool_call",
                tool_name=tool,
            )
            for tool in tools
        ],
        started_at=now,
        finished_at=now,
    )


def test_expected_tool_present() -> None:
    result = ToolSelectionEvaluator().evaluate(
        Scenario("scenario", "prompt", expected_tools=["search"]),
        make_trace("search"),
    )
    assert result.passed is True
    assert result.score == 1.0


def test_missing_expected_tool() -> None:
    result = ToolSelectionEvaluator().evaluate(
        Scenario("scenario", "prompt", expected_tools=["search"]),
        make_trace(),
    )
    assert result.passed is False
    assert result.score == 0.0
    assert "Missing expected tools: search" in result.findings


def test_forbidden_tool_used() -> None:
    result = ToolSelectionEvaluator().evaluate(
        Scenario("scenario", "prompt", forbidden_tools=["customer_database"]),
        make_trace("customer_database"),
    )
    assert result.passed is False
    assert "Forbidden tools used: customer_database" in result.findings


def test_empty_trace_with_no_constraints_passes() -> None:
    result = ToolSelectionEvaluator().evaluate(
        Scenario("scenario", "prompt"), make_trace()
    )
    assert result.passed is True
    assert result.score == 1.0


def test_duplicate_tool_calls_are_reported_but_not_inherently_failed() -> None:
    result = ToolSelectionEvaluator().evaluate(
        Scenario("scenario", "prompt", expected_tools=["search"]),
        make_trace("search", "search"),
    )
    assert result.passed is True
    assert result.metadata["tool_call_count"] == 2
    assert "Repeated tool calls observed: search x2" in result.findings


def test_max_tool_calls_counts_duplicates() -> None:
    result = ToolSelectionEvaluator().evaluate(
        Scenario("scenario", "prompt", max_tool_calls=1),
        make_trace("search", "search"),
    )
    assert result.passed is False
    assert result.score == 0.0
    assert "Tool call limit exceeded" in result.findings[0]
