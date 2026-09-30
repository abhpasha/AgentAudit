"""Deterministic evidence-provenance and grounding evaluator."""

from __future__ import annotations

from collections import Counter

from agentaudit.models import EvaluationResult, JSONValue, Scenario, Trace


class EvidenceGroundingEvaluator:
    """Evaluate deterministic evidence provenance and grounding requirements."""

    @property
    def name(self) -> str:
        return "evidence_grounding"

    def evaluate(self, scenario: Scenario, trace: Trace) -> EvaluationResult:
        findings: list[str] = []
        checks_total = 0
        checks_passed = 0

        evidence_ids = [item.id for item in trace.evidence]
        evidence_id_counts = Counter(evidence_ids)
        unique_evidence_ids = set(evidence_ids)

        duplicate_evidence_ids = sorted(
            evidence_id
            for evidence_id, count in evidence_id_counts.items()
            if count > 1
        )
        checks_total += 1
        if duplicate_evidence_ids:
            findings.append(
                "Duplicate evidence IDs: " + ", ".join(duplicate_evidence_ids)
            )
        else:
            checks_passed += 1

        referenced_evidence_ids = sorted(
            {
                evidence_id
                for step in trace.steps
                for evidence_id in step.evidence_ids
            }
        )
        broken_references = sorted(
            evidence_id
            for evidence_id in referenced_evidence_ids
            if evidence_id not in unique_evidence_ids
        )
        checks_total += 1
        if broken_references:
            findings.append(
                "Unresolved evidence references: " + ", ".join(broken_references)
            )
        else:
            checks_passed += 1

        available_sources = sorted({item.source for item in trace.evidence})

        missing_required_sources: list[str] = []
        if scenario.required_evidence_sources:
            checks_total += 1
            missing_required_sources = sorted(
                set(scenario.required_evidence_sources) - set(available_sources)
            )
            if missing_required_sources:
                findings.append(
                    "Missing required evidence sources: "
                    + ", ".join(missing_required_sources)
                )
            else:
                checks_passed += 1

        forbidden_sources_used: list[str] = []
        if scenario.forbidden_evidence_sources:
            checks_total += 1
            forbidden_sources_used = sorted(
                set(scenario.forbidden_evidence_sources) & set(available_sources)
            )
            if forbidden_sources_used:
                findings.append(
                    "Forbidden evidence sources used: "
                    + ", ".join(forbidden_sources_used)
                )
            else:
                checks_passed += 1

        evidence_count = len(unique_evidence_ids)
        if scenario.min_evidence_items > 0:
            checks_total += 1
            if evidence_count < scenario.min_evidence_items:
                findings.append(
                    "Minimum evidence requirement not met: "
                    f"{evidence_count} < {scenario.min_evidence_items}"
                )
            else:
                checks_passed += 1

        ungrounded_final_steps: list[int] = []
        missing_final_output = False
        if scenario.require_evidence_on_final_output:
            checks_total += 1
            final_steps = trace.final_output_steps
            if not final_steps:
                missing_final_output = True
                findings.append(
                    "Final-output evidence is required, but no final_output step "
                    "was recorded"
                )
            else:
                ungrounded_final_steps = [
                    index + 1
                    for index, step in enumerate(trace.steps)
                    if (
                        step.action_type == "final_output"
                        and not step.evidence_ids
                    )
                ]
                if ungrounded_final_steps:
                    rendered = ", ".join(
                        str(index) for index in ungrounded_final_steps
                    )
                    findings.append(
                        "Final-output steps missing evidence references: "
                        f"{rendered}"
                    )
                else:
                    checks_passed += 1

        passed = not findings
        score = checks_passed / checks_total if checks_total else 1.0

        metadata: dict[str, JSONValue] = {
            "checks_total": checks_total,
            "checks_passed": checks_passed,
            "evidence_count": evidence_count,
            "evidence_ids": sorted(unique_evidence_ids),
            "available_sources": available_sources,
            "referenced_evidence_ids": referenced_evidence_ids,
            "duplicate_evidence_ids": duplicate_evidence_ids,
            "broken_references": broken_references,
            "missing_required_sources": missing_required_sources,
            "forbidden_sources_used": forbidden_sources_used,
            "ungrounded_final_steps": ungrounded_final_steps,
            "missing_final_output": missing_final_output,
        }

        return EvaluationResult(
            evaluator_name=self.name,
            score=score,
            passed=passed,
            summary=(
                "Evidence provenance and grounding checks passed."
                if passed
                else "Evidence provenance and grounding checks failed."
            ),
            findings=findings,
            metadata=metadata,
        )
