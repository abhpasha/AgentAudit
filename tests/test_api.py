from datetime import datetime, timezone

import pytest

from agentaudit import BasicRunner, Scenario, Trace, TraceStep, evaluate


class GoodAgent:
    def run(self, scenario: Scenario) -> Trace:
        now = datetime.now(timezone.utc)
        return Trace(
            scenario_name=scenario.name,
            steps=[TraceStep(now, "agent", "tool_call", tool_name="lookup")],
            started_at=now,
            finished_at=now,
        )


class WrongScenarioAgent:
    def run(self, scenario: Scenario) -> Trace:
        now = datetime.now(timezone.utc)
        return Trace("wrong", [], now, now)


def test_evaluate_uses_default_deterministic_evaluators() -> None:
    scenario = Scenario(
        "scenario",
        "prompt",
        expected_tools=["lookup"],
        expected_tool_sequence=["lookup"],
    )
    results = evaluate(GoodAgent(), scenario)
    assert [result.evaluator_name for result in results] == [
        "tool_selection",
        "tool_sequence",
    ]
    assert all(result.passed for result in results)


def test_basic_runner_rejects_trace_for_other_scenario() -> None:
    with pytest.raises(ValueError, match="scenario_name"):
        BasicRunner().run(WrongScenarioAgent(), Scenario("scenario", "prompt"))
