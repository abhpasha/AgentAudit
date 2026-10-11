"""Framework-free regression-suite example for AgentAudit v0.2."""

from datetime import datetime, timezone

from agentaudit import EvaluationSuite, Scenario, Trace, TraceStep, evaluate_suite


class InventoryAgent:
    """Small deterministic agent used only to demonstrate suite evaluation."""

    def run(self, scenario: Scenario) -> Trace:
        now = datetime.now(timezone.utc)
        return Trace(
            scenario_name=scenario.name,
            steps=[
                TraceStep(
                    timestamp=now,
                    actor="agent",
                    action_type="tool_call",
                    tool_name="inventory_lookup",
                    input={"prompt": scenario.prompt},
                    output={"in_stock": True},
                    latency_ms=1.0,
                )
            ],
            started_at=now,
            finished_at=now,
        )


if __name__ == "__main__":
    suite = EvaluationSuite(
        name="inventory_regression",
        scenarios=[
            Scenario(
                name="stock_check_abc123",
                prompt="Check inventory for ABC123",
                expected_tools=["inventory_lookup"],
            ),
            Scenario(
                name="stock_check_xyz999",
                prompt="Check inventory for XYZ999",
                expected_tools=["inventory_lookup"],
            ),
        ],
    )

    result = evaluate_suite(InventoryAgent(), suite)
    print(result.to_json(indent=2))
