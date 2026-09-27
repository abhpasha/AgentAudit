from datetime import datetime, timezone

from agentaudit import Scenario, Trace, TraceStep
from agentaudit.evaluators import ToolSequenceEvaluator


def make_trace(*tools: str) -> Trace:
    now = datetime.now(timezone.utc)
    return Trace(
        scenario_name="scenario",
        steps=[
            TraceStep(now, "agent", "tool_call", tool_name=tool) for tool in tools
        ],
        started_at=now,
        finished_at=now,
    )


def test_correct_tool_sequence() -> None:
    result = ToolSequenceEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            expected_tool_sequence=["search", "fetch"],
        ),
        make_trace("search", "fetch"),
    )
    assert result.passed is True
    assert result.score == 1.0


def test_incorrect_tool_sequence() -> None:
    result = ToolSequenceEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            expected_tool_sequence=["search", "fetch"],
        ),
        make_trace("fetch", "search"),
    )
    assert result.passed is False
    assert result.score == 0.0
    assert "Sequence mismatch at position 1" in result.findings[0]


def test_empty_trace_fails_when_sequence_expected() -> None:
    result = ToolSequenceEvaluator().evaluate(
        Scenario("scenario", "prompt", expected_tool_sequence=["search"]),
        make_trace(),
    )
    assert result.passed is False
    assert "Sequence ended early" in result.findings[0]


def test_duplicate_call_breaks_exact_sequence() -> None:
    result = ToolSequenceEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            expected_tool_sequence=["search", "fetch"],
        ),
        make_trace("search", "search", "fetch"),
    )
    assert result.passed is False
    assert result.score < 1.0


def test_no_expected_sequence_is_noop() -> None:
    result = ToolSequenceEvaluator().evaluate(
        Scenario("scenario", "prompt"), make_trace("search")
    )
    assert result.passed is True
    assert result.score == 1.0
