# Proposed v0.2 Public API

This document is the implementation contract for Milestone 2. It is intentionally framework-agnostic and Python 3.10+ compatible.

## Core models

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, TypeAlias

JSONPrimitive: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONPrimitive | list["JSONValue"] | dict[str, "JSONValue"]


@dataclass(slots=True)
class Scenario:
    # v0.1 fields: preserve order for compatibility
    name: str
    prompt: str
    expected_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    expected_tool_sequence: list[str] = field(default_factory=list)
    max_tool_calls: int | None = None
    requires_human_approval: bool = False
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    # v0.2 approval policy
    approval_required_before: list[str] = field(default_factory=list)

    # v0.2 latency policy
    max_total_latency_ms: float | None = None
    max_step_latency_ms: float | None = None
    tool_latency_limits_ms: dict[str, float] = field(default_factory=dict)

    # v0.2 failure policy
    max_errors: int = 0
    allowed_error_types: list[str] = field(default_factory=list)
    max_retries_per_tool: int | None = None

    # v0.2 evidence policy
    required_evidence_sources: list[str] = field(default_factory=list)
    forbidden_evidence_sources: list[str] = field(default_factory=list)
    min_evidence_items: int = 0
    require_evidence_on_final_output: bool = False


@dataclass(slots=True, frozen=True)
class Evidence:
    id: str
    source: str
    content: JSONValue = None
    uri: str | None = None
    content_hash: str | None = None
    retrieved_at: datetime | None = None
    metadata: dict[str, JSONValue] = field(default_factory=dict)


@dataclass(slots=True)
class TraceStep:
    timestamp: datetime
    actor: str
    action_type: str
    tool_name: str | None = None
    input: JSONValue = None
    output: JSONValue = None
    latency_ms: float | None = None
    error: str | None = None
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    evidence_ids: list[str] = field(default_factory=list)
    approval_id: str | None = None
    error_type: str | None = None
    retryable: bool | None = None
    attempt: int | None = None


@dataclass(slots=True)
class Trace:
    scenario_name: str
    steps: list[TraceStep]
    started_at: datetime
    finished_at: datetime
    metadata: dict[str, JSONValue] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)


@dataclass(slots=True)
class EvaluationResult:
    evaluator_name: str
    score: float
    passed: bool
    summary: str
    findings: list[str] = field(default_factory=list)
    metadata: dict[str, JSONValue] = field(default_factory=dict)


@dataclass(slots=True)
class EvaluationSuite:
    name: str
    scenarios: list[Scenario]
    metadata: dict[str, JSONValue] = field(default_factory=dict)


@dataclass(slots=True)
class ScenarioEvaluation:
    scenario_name: str
    trace: Trace
    results: list[EvaluationResult]
    passed: bool
    score: float
    metadata: dict[str, JSONValue] = field(default_factory=dict)


@dataclass(slots=True)
class SuiteResult:
    suite_name: str
    scenario_results: list[ScenarioEvaluation]
    passed: bool
    score: float
    metadata: dict[str, JSONValue] = field(default_factory=dict)
```

## Evaluator protocol

```python
class Evaluator(Protocol):
    @property
    def name(self) -> str:
        ...

    def evaluate(
        self,
        scenario: Scenario,
        trace: Trace,
    ) -> EvaluationResult:
        ...
```

## New deterministic evaluators

```python
class TraceIntegrityEvaluator:
    @property
    def name(self) -> str:
        return "trace_integrity"

    def evaluate(self, scenario: Scenario, trace: Trace) -> EvaluationResult:
        ...


class HumanApprovalEvaluator:
    @property
    def name(self) -> str:
        return "human_approval"

    def evaluate(self, scenario: Scenario, trace: Trace) -> EvaluationResult:
        ...


class LatencyEvaluator:
    @property
    def name(self) -> str:
        return "latency"

    def evaluate(self, scenario: Scenario, trace: Trace) -> EvaluationResult:
        ...


class ExecutionFailureEvaluator:
    @property
    def name(self) -> str:
        return "execution_failure"

    def evaluate(self, scenario: Scenario, trace: Trace) -> EvaluationResult:
        ...


class EvidenceGroundingEvaluator:
    @property
    def name(self) -> str:
        return "evidence_grounding"

    def evaluate(self, scenario: Scenario, trace: Trace) -> EvaluationResult:
        ...
```

## High-level API

```python
from collections.abc import Sequence


def run_evaluation(
    agent: Agent,
    scenario: Scenario,
    *,
    runner: Runner | None = None,
    evaluators: Sequence[Evaluator] | None = None,
) -> ScenarioEvaluation:
    ...


def evaluate_suite(
    agent: Agent,
    suite: EvaluationSuite,
    *,
    runner: Runner | None = None,
    evaluators: Sequence[Evaluator] | None = None,
) -> SuiteResult:
    ...


def evaluate(
    agent: Agent,
    scenario: Scenario,
    *,
    runner: Runner | None = None,
    evaluators: Sequence[Evaluator] | None = None,
) -> list[EvaluationResult]:
    """Backwards-compatible v0.1 API."""
    return run_evaluation(
        agent,
        scenario,
        runner=runner,
        evaluators=evaluators,
    ).results
```

Proposed default evaluator set:

```python
_DEFAULT_EVALUATORS: tuple[Evaluator, ...] = (
    TraceIntegrityEvaluator(),
    ToolSelectionEvaluator(),
    ToolSequenceEvaluator(),
    HumanApprovalEvaluator(),
    LatencyEvaluator(),
    ExecutionFailureEvaluator(),
    EvidenceGroundingEvaluator(),
)
```

## Compatibility rule

New fields should be appended to existing dataclasses rather than inserted before v0.1 fields. This preserves existing positional construction as far as practical during the pre-1.0 period.
