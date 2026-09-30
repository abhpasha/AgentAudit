from datetime import datetime, timedelta, timezone

import pytest

from agentaudit import (
    Evidence,
    EvidenceGroundingEvaluator,
    Scenario,
    Trace,
    TraceStep,
)

START = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def make_trace(
    *steps: TraceStep,
    evidence: list[Evidence] | None = None,
) -> Trace:
    return Trace(
        scenario_name="scenario",
        steps=list(steps),
        started_at=START,
        finished_at=START + timedelta(seconds=1),
        evidence=evidence or [],
    )


def evidence_item(
    evidence_id: str,
    source: str = "inventory_database",
) -> Evidence:
    return Evidence(
        id=evidence_id,
        source=source,
        content={"id": evidence_id},
    )


def final_step(
    offset_ms: int = 10,
    *,
    evidence_ids: list[str] | None = None,
) -> TraceStep:
    return TraceStep(
        START + timedelta(milliseconds=offset_ms),
        "agent",
        "final_output",
        output={"answer": "done"},
        evidence_ids=evidence_ids or [],
    )


def test_clean_trace_without_evidence_policy_passes() -> None:
    result = EvidenceGroundingEvaluator().evaluate(
        Scenario("scenario", "prompt"),
        make_trace(),
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.metadata["checks_total"] == 2


def test_required_evidence_source_present_passes() -> None:
    result = EvidenceGroundingEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            required_evidence_sources=["inventory_database"],
        ),
        make_trace(evidence=[evidence_item("ev-1")]),
    )

    assert result.passed is True
    assert result.metadata["available_sources"] == ["inventory_database"]


def test_missing_required_evidence_source_fails() -> None:
    result = EvidenceGroundingEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            required_evidence_sources=["inventory_database"],
        ),
        make_trace(
            evidence=[evidence_item("ev-1", source="product_catalog")]
        ),
    )

    assert result.passed is False
    assert result.metadata["missing_required_sources"] == [
        "inventory_database"
    ]
    assert "Missing required evidence sources" in result.findings[0]


def test_forbidden_evidence_source_fails() -> None:
    result = EvidenceGroundingEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            forbidden_evidence_sources=["customer_database"],
        ),
        make_trace(
            evidence=[evidence_item("ev-1", source="customer_database")]
        ),
    )

    assert result.passed is False
    assert result.metadata["forbidden_sources_used"] == ["customer_database"]


def test_valid_evidence_reference_passes() -> None:
    result = EvidenceGroundingEvaluator().evaluate(
        Scenario("scenario", "prompt"),
        make_trace(
            final_step(evidence_ids=["ev-1"]),
            evidence=[evidence_item("ev-1")],
        ),
    )

    assert result.passed is True
    assert result.metadata["referenced_evidence_ids"] == ["ev-1"]


def test_broken_evidence_reference_fails() -> None:
    result = EvidenceGroundingEvaluator().evaluate(
        Scenario("scenario", "prompt"),
        make_trace(final_step(evidence_ids=["missing"])),
    )

    assert result.passed is False
    assert result.metadata["broken_references"] == ["missing"]
    assert "Unresolved evidence references" in result.findings[0]


def test_duplicate_evidence_ids_fail() -> None:
    result = EvidenceGroundingEvaluator().evaluate(
        Scenario("scenario", "prompt"),
        make_trace(
            evidence=[
                evidence_item("ev-1", source="inventory_database"),
                evidence_item("ev-1", source="product_catalog"),
            ]
        ),
    )

    assert result.passed is False
    assert result.metadata["duplicate_evidence_ids"] == ["ev-1"]


def test_minimum_evidence_counts_unique_ids() -> None:
    result = EvidenceGroundingEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            min_evidence_items=2,
        ),
        make_trace(
            evidence=[
                evidence_item("ev-1"),
                evidence_item("ev-1"),
            ]
        ),
    )

    assert result.passed is False
    assert result.metadata["evidence_count"] == 1
    assert any(
        "Minimum evidence requirement not met" in finding
        for finding in result.findings
    )


def test_minimum_evidence_requirement_passes() -> None:
    result = EvidenceGroundingEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            min_evidence_items=2,
        ),
        make_trace(
            evidence=[
                evidence_item("ev-1"),
                evidence_item("ev-2"),
            ]
        ),
    )

    assert result.passed is True


def test_final_output_grounding_passes_with_evidence_reference() -> None:
    result = EvidenceGroundingEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            require_evidence_on_final_output=True,
        ),
        make_trace(
            final_step(evidence_ids=["ev-1"]),
            evidence=[evidence_item("ev-1")],
        ),
    )

    assert result.passed is True
    assert result.metadata["ungrounded_final_steps"] == []


def test_final_output_without_evidence_reference_fails() -> None:
    result = EvidenceGroundingEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            require_evidence_on_final_output=True,
        ),
        make_trace(final_step()),
    )

    assert result.passed is False
    assert result.metadata["ungrounded_final_steps"] == [1]
    assert "Final-output steps missing evidence references" in result.findings[0]


def test_missing_final_output_fails_when_grounding_is_required() -> None:
    result = EvidenceGroundingEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            require_evidence_on_final_output=True,
        ),
        make_trace(evidence=[evidence_item("ev-1")]),
    )

    assert result.passed is False
    assert result.metadata["missing_final_output"] is True


def test_all_final_output_steps_must_be_grounded() -> None:
    result = EvidenceGroundingEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            require_evidence_on_final_output=True,
        ),
        make_trace(
            final_step(10, evidence_ids=["ev-1"]),
            final_step(20),
            evidence=[evidence_item("ev-1")],
        ),
    )

    assert result.passed is False
    assert result.metadata["ungrounded_final_steps"] == [2]


def test_combined_policy_score_is_deterministic() -> None:
    result = EvidenceGroundingEvaluator().evaluate(
        Scenario(
            "scenario",
            "prompt",
            required_evidence_sources=["inventory_database"],
            forbidden_evidence_sources=["customer_database"],
            min_evidence_items=1,
            require_evidence_on_final_output=True,
        ),
        make_trace(
            final_step(evidence_ids=["ev-1"]),
            evidence=[
                evidence_item("ev-1", source="inventory_database"),
                evidence_item("ev-2", source="customer_database"),
            ],
        ),
    )

    assert result.passed is False
    assert result.score == pytest.approx(5 / 6)
    assert result.metadata["checks_total"] == 6
    assert result.metadata["checks_passed"] == 5
