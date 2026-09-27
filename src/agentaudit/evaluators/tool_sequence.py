"""Deterministic tool-sequence evaluator."""

from __future__ import annotations

from agentaudit.models import EvaluationResult, JSONValue, Scenario, Trace


class ToolSequenceEvaluator:
    """Require the observed tool-call sequence to exactly match expectation."""

    @property
    def name(self) -> str:
        return "tool_sequence"

    def evaluate(self, scenario: Scenario, trace: Trace) -> EvaluationResult:
        expected = scenario.expected_tool_sequence
        actual = trace.tool_names

        if not expected:
            no_expectation_metadata: dict[str, JSONValue] = {
                "expected_sequence": [],
                "actual_sequence": [tool for tool in actual],
            }
            return EvaluationResult(
                evaluator_name=self.name,
                score=1.0,
                passed=True,
                summary="No expected tool sequence configured.",
                metadata=no_expectation_metadata,
            )

        passed = actual == expected
        denominator = max(len(expected), len(actual), 1)
        positional_matches = sum(
            expected[index] == actual[index]
            for index in range(min(len(expected), len(actual)))
        )
        score = positional_matches / denominator

        findings: list[str] = []
        if not passed:
            mismatch_index = next(
                (
                    index
                    for index in range(min(len(expected), len(actual)))
                    if expected[index] != actual[index]
                ),
                min(len(expected), len(actual)),
            )
            if mismatch_index < len(expected) and mismatch_index < len(actual):
                findings.append(
                    f"Sequence mismatch at position {mismatch_index + 1}: "
                    f"expected {expected[mismatch_index]!r}, "
                    f"observed {actual[mismatch_index]!r}"
                )
            elif len(actual) < len(expected):
                findings.append(
                    f"Sequence ended early at position {mismatch_index + 1}; "
                    f"expected {expected[mismatch_index]!r}"
                )
            else:
                findings.append(
                    f"Unexpected extra tool call at position {mismatch_index + 1}: "
                    f"{actual[mismatch_index]!r}"
                )

        expected_json: list[JSONValue] = [tool for tool in expected]
        actual_json: list[JSONValue] = [tool for tool in actual]
        metadata: dict[str, JSONValue] = {
            "expected_sequence": expected_json,
            "actual_sequence": actual_json,
        }
        return EvaluationResult(
            evaluator_name=self.name,
            score=score,
            passed=passed,
            summary=(
                "Tool sequence matches expectation."
                if passed
                else "Tool sequence does not match expectation."
            ),
            findings=findings,
            metadata=metadata,
        )
