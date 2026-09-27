"""Deterministic tool-selection evaluator."""

from __future__ import annotations

from collections import Counter

from agentaudit.models import EvaluationResult, JSONValue, Scenario, Trace


class ToolSelectionEvaluator:
    """Check required, forbidden, and maximum tool-call constraints."""

    @property
    def name(self) -> str:
        return "tool_selection"

    def evaluate(self, scenario: Scenario, trace: Trace) -> EvaluationResult:
        tool_names = trace.tool_names
        counts = Counter(tool_names)
        used = set(tool_names)

        missing = [tool for tool in scenario.expected_tools if tool not in used]
        forbidden_used = [tool for tool in scenario.forbidden_tools if tool in used]
        max_exceeded = (
            scenario.max_tool_calls is not None
            and len(tool_names) > scenario.max_tool_calls
        )

        checks_total = len(scenario.expected_tools) + len(scenario.forbidden_tools)
        checks_passed = len(scenario.expected_tools) - len(missing)
        checks_passed += len(scenario.forbidden_tools) - len(forbidden_used)
        if scenario.max_tool_calls is not None:
            checks_total += 1
            checks_passed += int(not max_exceeded)

        score = 1.0 if checks_total == 0 else checks_passed / checks_total
        passed = not missing and not forbidden_used and not max_exceeded

        findings: list[str] = []
        if missing:
            findings.append(f"Missing expected tools: {', '.join(missing)}")
        if forbidden_used:
            findings.append(f"Forbidden tools used: {', '.join(forbidden_used)}")
        if max_exceeded:
            findings.append(
                f"Tool call limit exceeded: {len(tool_names)} calls made; "
                f"maximum is {scenario.max_tool_calls}"
            )

        duplicates = {tool: count for tool, count in counts.items() if count > 1}
        if duplicates:
            rendered = ", ".join(
                f"{tool} x{count}" for tool, count in sorted(duplicates.items())
            )
            findings.append(f"Repeated tool calls observed: {rendered}")

        tool_call_counts: dict[str, JSONValue] = {
            tool: count for tool, count in sorted(counts.items())
        }
        missing_json: list[JSONValue] = [tool for tool in missing]
        forbidden_json: list[JSONValue] = [tool for tool in forbidden_used]
        metadata: dict[str, JSONValue] = {
            "tool_call_count": len(tool_names),
            "tool_call_counts": tool_call_counts,
            "missing_expected_tools": missing_json,
            "forbidden_tools_used": forbidden_json,
        }

        summary = (
            "Tool selection checks passed."
            if passed
            else "Tool selection checks failed."
        )
        return EvaluationResult(
            evaluator_name=self.name,
            score=score,
            passed=passed,
            summary=summary,
            findings=findings,
            metadata=metadata,
        )
