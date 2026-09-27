"""Minimal framework-free AgentAudit example."""

from datetime import datetime, timezone

from agentaudit import Scenario, Trace, TraceStep, evaluate


class InventoryAgent:
    """Small deterministic example agent with one fake tool call."""

    def run(self, scenario: Scenario) -> Trace:
        started_at = datetime.now(timezone.utc)
        steps = [
            TraceStep(
                timestamp=started_at,
                actor="agent",
                action_type="tool_call",
                tool_name="inventory_lookup",
                input={"sku": "ABC123"},
                output={"sku": "ABC123", "in_stock": True, "quantity": 12},
                latency_ms=1.2,
            )
        ]
        finished_at = datetime.now(timezone.utc)
        return Trace(
            scenario_name=scenario.name,
            steps=steps,
            started_at=started_at,
            finished_at=finished_at,
        )


if __name__ == "__main__":
    scenario = Scenario(
        name="stock_check",
        prompt="Check inventory for ABC123",
        expected_tools=["inventory_lookup"],
        forbidden_tools=["customer_database"],
        expected_tool_sequence=["inventory_lookup"],
        max_tool_calls=1,
    )
    results = evaluate(InventoryAgent(), scenario)
    for result in results:
        print(result.to_json(indent=2))
