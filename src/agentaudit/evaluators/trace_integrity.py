"""Deterministic trace-integrity evaluator."""

from __future__ import annotations

from collections import Counter

from agentaudit.models import EvaluationResult, JSONValue, Scenario, Trace

_APPROVAL_ACTIONS = {
    "human_approval_requested",
    "human_approval_granted",
    "human_approval_denied",
}


class TraceIntegrityEvaluator:
    """Validate cross-record and sequencing invariants in an execution trace."""

    @property
    def name(self) -> str:
        return "trace_integrity"

    def evaluate(self, scenario: Scenario, trace: Trace) -> EvaluationResult:
        findings: list[str] = []
        checks_total = 8
        checks_passed = 0

        if trace.scenario_name == scenario.name:
            checks_passed += 1
        else:
            findings.append(
                "Trace scenario_name does not match Scenario.name: "
                f"{trace.scenario_name!r} != {scenario.name!r}"
            )

        evidence_counts = Counter(item.id for item in trace.evidence)
        duplicate_evidence_ids = sorted(
            evidence_id
            for evidence_id, count in evidence_counts.items()
            if count > 1
        )
        if not duplicate_evidence_ids:
            checks_passed += 1
        else:
            findings.append(
                "Duplicate evidence IDs: " + ", ".join(duplicate_evidence_ids)
            )

        known_evidence_ids = set(evidence_counts)
        broken_references = sorted(
            {
                evidence_id
                for step in trace.steps
                for evidence_id in step.evidence_ids
                if evidence_id not in known_evidence_ids
            }
        )
        if not broken_references:
            checks_passed += 1
        else:
            findings.append(
                "Unresolved evidence references: " + ", ".join(broken_references)
            )

        timestamps = [step.timestamp for step in trace.steps]
        if all(
            current <= following
            for current, following in zip(timestamps, timestamps[1:])
        ):
            checks_passed += 1
        else:
            findings.append("Trace step timestamps are not non-decreasing")

        outside_bounds = [
            index + 1
            for index, step in enumerate(trace.steps)
            if step.timestamp < trace.started_at or step.timestamp > trace.finished_at
        ]
        if not outside_bounds:
            checks_passed += 1
        else:
            rendered = ", ".join(str(index) for index in outside_bounds)
            findings.append(f"Trace steps outside trace time bounds: {rendered}")

        tool_calls_without_name = [
            index + 1
            for index, step in enumerate(trace.steps)
            if step.action_type == "tool_call" and step.tool_name is None
        ]
        if not tool_calls_without_name:
            checks_passed += 1
        else:
            rendered = ", ".join(str(index) for index in tool_calls_without_name)
            findings.append(f"tool_call steps missing tool_name: {rendered}")

        approval_steps_without_id = [
            index + 1
            for index, step in enumerate(trace.steps)
            if step.action_type in _APPROVAL_ACTIONS and step.approval_id is None
        ]
        if not approval_steps_without_id:
            checks_passed += 1
        else:
            rendered = ", ".join(str(index) for index in approval_steps_without_id)
            findings.append(f"Approval steps missing approval_id: {rendered}")

        invalid_attempts = [
            index + 1
            for index, step in enumerate(trace.steps)
            if step.attempt is not None and step.attempt < 1
        ]
        errors_without_error = [
            index + 1
            for index, step in enumerate(trace.steps)
            if step.error_type is not None and step.error is None
        ]
        if not invalid_attempts and not errors_without_error:
            checks_passed += 1
        else:
            if invalid_attempts:
                rendered = ", ".join(str(index) for index in invalid_attempts)
                findings.append(f"Trace steps with attempt < 1: {rendered}")
            if errors_without_error:
                rendered = ", ".join(str(index) for index in errors_without_error)
                findings.append(
                    "Trace steps with error_type but no error: " + rendered
                )

        passed = not findings
        metadata: dict[str, JSONValue] = {
            "checks_total": checks_total,
            "checks_passed": checks_passed,
            "duplicate_evidence_ids": [
                evidence_id for evidence_id in duplicate_evidence_ids
            ],
            "broken_evidence_references": [
                evidence_id for evidence_id in broken_references
            ],
        }
        return EvaluationResult(
            evaluator_name=self.name,
            score=checks_passed / checks_total,
            passed=passed,
            summary=(
                "Trace integrity checks passed."
                if passed
                else "Trace integrity checks failed."
            ),
            findings=findings,
            metadata=metadata,
        )
