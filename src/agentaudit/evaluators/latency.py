"""Deterministic latency-budget evaluator."""

from __future__ import annotations

from agentaudit.models import EvaluationResult, JSONValue, Scenario, Trace


class LatencyEvaluator:
    """Evaluate total, step-level, and tool-specific latency budgets."""

    @property
    def name(self) -> str:
        return "latency"

    def evaluate(self, scenario: Scenario, trace: Trace) -> EvaluationResult:
        policy_enabled = (
            scenario.max_total_latency_ms is not None
            or scenario.max_step_latency_ms is not None
            or bool(scenario.tool_latency_limits_ms)
        )

        if not policy_enabled:
            metadata: dict[str, JSONValue] = {
                "checks_total": 0,
                "checks_passed": 0,
                "total_latency_ms": trace.total_latency_ms,
            }
            return EvaluationResult(
                evaluator_name=self.name,
                score=1.0,
                passed=True,
                summary="No latency budget configured.",
                metadata=metadata,
            )

        findings: list[str] = []
        checks_total = 0
        checks_passed = 0

        total_latency_ms = trace.total_latency_ms
        if scenario.max_total_latency_ms is not None:
            checks_total += 1
            if total_latency_ms <= scenario.max_total_latency_ms:
                checks_passed += 1
            else:
                findings.append(
                    "Total latency exceeded budget: "
                    f"{total_latency_ms:.3f} ms > "
                    f"{scenario.max_total_latency_ms:.3f} ms"
                )

        missing_step_latency: list[JSONValue] = []
        steps_over_budget: list[JSONValue] = []

        if scenario.max_step_latency_ms is not None:
            for index, step in enumerate(trace.steps, start=1):
                checks_total += 1
                if step.latency_ms is None:
                    missing_step_latency.append(index)
                    continue
                if step.latency_ms <= scenario.max_step_latency_ms:
                    checks_passed += 1
                    continue
                steps_over_budget.append(
                    {
                        "step": index,
                        "latency_ms": step.latency_ms,
                        "budget_ms": scenario.max_step_latency_ms,
                    }
                )

        if missing_step_latency:
            rendered = ", ".join(str(index) for index in missing_step_latency)
            findings.append(
                "Missing latency_ms for steps under max_step_latency_ms policy: "
                f"{rendered}"
            )

        if steps_over_budget:
            rendered = ", ".join(
                (
                    f"step {item['step']} "
                    f"({item['latency_ms']} ms > {item['budget_ms']} ms)"
                )
                for item in steps_over_budget
                if isinstance(item, dict)
            )
            findings.append(f"Step latency budget exceeded: {rendered}")

        missing_tool_latency: list[JSONValue] = []
        tools_over_budget: list[JSONValue] = []

        for index, step in enumerate(trace.steps, start=1):
            if step.action_type != "tool_call" or step.tool_name is None:
                continue

            budget_ms = scenario.tool_latency_limits_ms.get(step.tool_name)
            if budget_ms is None:
                continue

            checks_total += 1
            if step.latency_ms is None:
                missing_tool_latency.append(
                    {
                        "step": index,
                        "tool_name": step.tool_name,
                        "budget_ms": budget_ms,
                    }
                )
                continue

            if step.latency_ms <= budget_ms:
                checks_passed += 1
                continue

            tools_over_budget.append(
                {
                    "step": index,
                    "tool_name": step.tool_name,
                    "latency_ms": step.latency_ms,
                    "budget_ms": budget_ms,
                }
            )

        if missing_tool_latency:
            rendered = ", ".join(
                f"step {item['step']} ({item['tool_name']})"
                for item in missing_tool_latency
                if isinstance(item, dict)
            )
            findings.append(
                "Missing latency_ms for tool calls with configured budgets: "
                f"{rendered}"
            )

        if tools_over_budget:
            rendered = ", ".join(
                (
                    f"step {item['step']} {item['tool_name']} "
                    f"({item['latency_ms']} ms > {item['budget_ms']} ms)"
                )
                for item in tools_over_budget
                if isinstance(item, dict)
            )
            findings.append(f"Tool latency budget exceeded: {rendered}")

        passed = not findings
        score = checks_passed / checks_total if checks_total else 1.0

        metadata = {
            "checks_total": checks_total,
            "checks_passed": checks_passed,
            "total_latency_ms": total_latency_ms,
            "max_total_latency_ms": scenario.max_total_latency_ms,
            "max_step_latency_ms": scenario.max_step_latency_ms,
            "missing_step_latency": missing_step_latency,
            "steps_over_budget": steps_over_budget,
            "missing_tool_latency": missing_tool_latency,
            "tools_over_budget": tools_over_budget,
        }

        return EvaluationResult(
            evaluator_name=self.name,
            score=score,
            passed=passed,
            summary=(
                "Latency budget checks passed."
                if passed
                else "Latency budget checks failed."
            ),
            findings=findings,
            metadata=metadata,
        )
