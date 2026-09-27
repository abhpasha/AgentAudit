"""Core domain models for AgentAudit."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypeAlias

JSONPrimitive: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONPrimitive | list["JSONValue"] | dict[str, "JSONValue"]


def _validate_json_value(value: JSONValue, *, path: str = "value") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must not contain NaN or infinity")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} keys must be strings")
            _validate_json_value(item, path=f"{path}.{key}")
        return
    raise TypeError(f"{path} must be JSON-serialisable, got {type(value).__name__}")


def _validate_datetime(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _validate_string_list(values: list[str], *, field_name: str) -> None:
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must contain only non-empty strings")


def _validate_unique_string_list(values: list[str], *, field_name: str) -> None:
    _validate_string_list(values, field_name=field_name)
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must not contain duplicates")


def _validate_nonnegative_number(value: float | int, *, field_name: str) -> None:
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError(f"{field_name} must be a finite number greater than or equal to zero")


@dataclass(slots=True)
class Scenario:
    """A deterministic description of expected agent behaviour."""

    # v0.1 fields: preserve order for backwards compatibility.
    name: str
    prompt: str
    expected_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    expected_tool_sequence: list[str] = field(default_factory=list)
    max_tool_calls: int | None = None
    requires_human_approval: bool = False
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    # v0.2 governance policy.
    approval_required_before: list[str] = field(default_factory=list)
    max_total_latency_ms: float | None = None
    max_step_latency_ms: float | None = None
    tool_latency_limits_ms: dict[str, float] = field(default_factory=dict)
    max_errors: int = 0
    allowed_error_types: list[str] = field(default_factory=list)
    max_retries_per_tool: int | None = None
    required_evidence_sources: list[str] = field(default_factory=list)
    forbidden_evidence_sources: list[str] = field(default_factory=list)
    min_evidence_items: int = 0
    require_evidence_on_final_output: bool = False

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Scenario name must not be empty")
        if not self.prompt.strip():
            raise ValueError("Scenario prompt must not be empty")

        _validate_unique_string_list(self.expected_tools, field_name="expected_tools")
        _validate_unique_string_list(self.forbidden_tools, field_name="forbidden_tools")
        _validate_string_list(
            self.expected_tool_sequence,
            field_name="expected_tool_sequence",
        )
        _validate_unique_string_list(
            self.approval_required_before,
            field_name="approval_required_before",
        )
        _validate_unique_string_list(
            self.allowed_error_types,
            field_name="allowed_error_types",
        )
        _validate_unique_string_list(
            self.required_evidence_sources,
            field_name="required_evidence_sources",
        )
        _validate_unique_string_list(
            self.forbidden_evidence_sources,
            field_name="forbidden_evidence_sources",
        )

        tool_overlap = set(self.expected_tools) & set(self.forbidden_tools)
        if tool_overlap:
            names = ", ".join(sorted(tool_overlap))
            raise ValueError(f"Tools cannot be both expected and forbidden: {names}")

        evidence_overlap = set(self.required_evidence_sources) & set(
            self.forbidden_evidence_sources
        )
        if evidence_overlap:
            names = ", ".join(sorted(evidence_overlap))
            raise ValueError(
                f"Evidence sources cannot be both required and forbidden: {names}"
            )

        if self.max_tool_calls is not None and self.max_tool_calls < 0:
            raise ValueError("max_tool_calls must be greater than or equal to zero")
        if self.max_errors < 0:
            raise ValueError("max_errors must be greater than or equal to zero")
        if self.max_retries_per_tool is not None and self.max_retries_per_tool < 0:
            raise ValueError(
                "max_retries_per_tool must be greater than or equal to zero"
            )
        if self.min_evidence_items < 0:
            raise ValueError("min_evidence_items must be greater than or equal to zero")

        if self.max_total_latency_ms is not None:
            _validate_nonnegative_number(
                self.max_total_latency_ms,
                field_name="max_total_latency_ms",
            )
        if self.max_step_latency_ms is not None:
            _validate_nonnegative_number(
                self.max_step_latency_ms,
                field_name="max_step_latency_ms",
            )

        for tool_name, limit in self.tool_latency_limits_ms.items():
            if not isinstance(tool_name, str) or not tool_name.strip():
                raise ValueError(
                    "tool_latency_limits_ms keys must be non-empty strings"
                )
            _validate_nonnegative_number(
                limit,
                field_name=f"tool_latency_limits_ms[{tool_name!r}]",
            )

        _validate_json_value(self.metadata, path="metadata")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "prompt": self.prompt,
            "expected_tools": list(self.expected_tools),
            "forbidden_tools": list(self.forbidden_tools),
            "expected_tool_sequence": list(self.expected_tool_sequence),
            "max_tool_calls": self.max_tool_calls,
            "requires_human_approval": self.requires_human_approval,
            "metadata": dict(self.metadata),
            "approval_required_before": list(self.approval_required_before),
            "max_total_latency_ms": self.max_total_latency_ms,
            "max_step_latency_ms": self.max_step_latency_ms,
            "tool_latency_limits_ms": dict(self.tool_latency_limits_ms),
            "max_errors": self.max_errors,
            "allowed_error_types": list(self.allowed_error_types),
            "max_retries_per_tool": self.max_retries_per_tool,
            "required_evidence_sources": list(self.required_evidence_sources),
            "forbidden_evidence_sources": list(self.forbidden_evidence_sources),
            "min_evidence_items": self.min_evidence_items,
            "require_evidence_on_final_output": self.require_evidence_on_final_output,
        }

    def to_json(self, *, indent: int | None = None) -> str:
        return json.dumps(
            self.to_dict(),
            indent=indent,
            sort_keys=True,
            allow_nan=False,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Scenario:
        return cls(
            name=data["name"],
            prompt=data["prompt"],
            expected_tools=data.get("expected_tools", []),
            forbidden_tools=data.get("forbidden_tools", []),
            expected_tool_sequence=data.get("expected_tool_sequence", []),
            max_tool_calls=data.get("max_tool_calls"),
            requires_human_approval=data.get("requires_human_approval", False),
            metadata=data.get("metadata", {}),
            approval_required_before=data.get("approval_required_before", []),
            max_total_latency_ms=data.get("max_total_latency_ms"),
            max_step_latency_ms=data.get("max_step_latency_ms"),
            tool_latency_limits_ms=data.get("tool_latency_limits_ms", {}),
            max_errors=data.get("max_errors", 0),
            allowed_error_types=data.get("allowed_error_types", []),
            max_retries_per_tool=data.get("max_retries_per_tool"),
            required_evidence_sources=data.get("required_evidence_sources", []),
            forbidden_evidence_sources=data.get("forbidden_evidence_sources", []),
            min_evidence_items=data.get("min_evidence_items", 0),
            require_evidence_on_final_output=data.get(
                "require_evidence_on_final_output",
                False,
            ),
        )

    @classmethod
    def from_json(cls, payload: str) -> Scenario:
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise TypeError("Scenario JSON must decode to an object")
        return cls.from_dict(data)


@dataclass(slots=True, frozen=True)
class Evidence:
    """One provenance item retrieved or produced during agent execution."""

    id: str
    source: str
    content: JSONValue = None
    uri: str | None = None
    content_hash: str | None = None
    retrieved_at: datetime | None = None
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Evidence id must not be empty")
        if not self.source.strip():
            raise ValueError("Evidence source must not be empty")
        if self.uri is not None and not self.uri.strip():
            raise ValueError("Evidence uri must be None or a non-empty string")
        if self.content_hash is not None and not self.content_hash.strip():
            raise ValueError("Evidence content_hash must be None or a non-empty string")
        if self.retrieved_at is not None:
            _validate_datetime(self.retrieved_at, field_name="retrieved_at")
        _validate_json_value(self.content, path="content")
        _validate_json_value(self.metadata, path="metadata")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "content": self.content,
            "uri": self.uri,
            "content_hash": self.content_hash,
            "retrieved_at": (
                self.retrieved_at.isoformat()
                if self.retrieved_at is not None
                else None
            ),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Evidence:
        retrieved_at = data.get("retrieved_at")
        return cls(
            id=data["id"],
            source=data["source"],
            content=data.get("content"),
            uri=data.get("uri"),
            content_hash=data.get("content_hash"),
            retrieved_at=(
                datetime.fromisoformat(retrieved_at)
                if retrieved_at is not None
                else None
            ),
            metadata=data.get("metadata", {}),
        )


@dataclass(slots=True)
class TraceStep:
    """One observable step in an agent execution trace."""

    # v0.1 fields: preserve order for backwards compatibility.
    timestamp: datetime
    actor: str
    action_type: str
    tool_name: str | None = None
    input: JSONValue = None
    output: JSONValue = None
    latency_ms: float | None = None
    error: str | None = None
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    # v0.2 trace and governance fields.
    evidence_ids: list[str] = field(default_factory=list)
    approval_id: str | None = None
    error_type: str | None = None
    retryable: bool | None = None
    attempt: int | None = None

    def __post_init__(self) -> None:
        _validate_datetime(self.timestamp, field_name="timestamp")
        if not self.actor.strip():
            raise ValueError("TraceStep actor must not be empty")
        if not self.action_type.strip():
            raise ValueError("TraceStep action_type must not be empty")
        if self.tool_name is not None and not self.tool_name.strip():
            raise ValueError("tool_name must be None or a non-empty string")
        if self.latency_ms is not None:
            _validate_nonnegative_number(self.latency_ms, field_name="latency_ms")
        _validate_unique_string_list(self.evidence_ids, field_name="evidence_ids")
        if self.approval_id is not None and not self.approval_id.strip():
            raise ValueError("approval_id must be None or a non-empty string")
        if self.error_type is not None and not self.error_type.strip():
            raise ValueError("error_type must be None or a non-empty string")
        _validate_json_value(self.input, path="input")
        _validate_json_value(self.output, path="output")
        _validate_json_value(self.metadata, path="metadata")

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "action_type": self.action_type,
            "tool_name": self.tool_name,
            "input": self.input,
            "output": self.output,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "metadata": dict(self.metadata),
            "evidence_ids": list(self.evidence_ids),
            "approval_id": self.approval_id,
            "error_type": self.error_type,
            "retryable": self.retryable,
            "attempt": self.attempt,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceStep:
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            actor=data["actor"],
            action_type=data["action_type"],
            tool_name=data.get("tool_name"),
            input=data.get("input"),
            output=data.get("output"),
            latency_ms=data.get("latency_ms"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
            evidence_ids=data.get("evidence_ids", []),
            approval_id=data.get("approval_id"),
            error_type=data.get("error_type"),
            retryable=data.get("retryable"),
            attempt=data.get("attempt"),
        )


@dataclass(slots=True)
class Trace:
    """Complete, JSON-serialisable evidence from one scenario execution."""

    # v0.1 fields: preserve order for backwards compatibility.
    scenario_name: str
    steps: list[TraceStep]
    started_at: datetime
    finished_at: datetime
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    # v0.2 evidence store.
    evidence: list[Evidence] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.scenario_name.strip():
            raise ValueError("Trace scenario_name must not be empty")
        _validate_datetime(self.started_at, field_name="started_at")
        _validate_datetime(self.finished_at, field_name="finished_at")
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must not be before started_at")
        _validate_json_value(self.metadata, path="metadata")

    @property
    def tool_steps(self) -> list[TraceStep]:
        """Return steps that represent concrete tool calls."""
        return [
            step
            for step in self.steps
            if step.action_type == "tool_call" and step.tool_name is not None
        ]

    @property
    def tool_names(self) -> list[str]:
        """Return tool names in execution order, preserving duplicates."""
        return [step.tool_name for step in self.tool_steps if step.tool_name is not None]

    @property
    def error_steps(self) -> list[TraceStep]:
        """Return trace steps that contain an execution error."""
        return [step for step in self.steps if step.error is not None]

    @property
    def total_latency_ms(self) -> float:
        """Return wall-clock trace duration in milliseconds."""
        return (self.finished_at - self.started_at).total_seconds() * 1000.0

    @property
    def evidence_by_id(self) -> dict[str, Evidence]:
        """Return evidence indexed by ID.

        Duplicate IDs are intentionally surfaced by TraceIntegrityEvaluator.
        """
        return {item.id: item for item in self.evidence}

    @property
    def final_output_steps(self) -> list[TraceStep]:
        """Return steps explicitly marked as final outputs."""
        return [step for step in self.steps if step.action_type == "final_output"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "steps": [step.to_dict() for step in self.steps],
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "metadata": dict(self.metadata),
            "evidence": [item.to_dict() for item in self.evidence],
        }

    def to_json(self, *, indent: int | None = None) -> str:
        return json.dumps(
            self.to_dict(),
            indent=indent,
            sort_keys=True,
            allow_nan=False,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Trace:
        return cls(
            scenario_name=data["scenario_name"],
            steps=[TraceStep.from_dict(step) for step in data.get("steps", [])],
            started_at=datetime.fromisoformat(data["started_at"]),
            finished_at=datetime.fromisoformat(data["finished_at"]),
            metadata=data.get("metadata", {}),
            evidence=[Evidence.from_dict(item) for item in data.get("evidence", [])],
        )

    @classmethod
    def from_json(cls, payload: str) -> Trace:
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise TypeError("Trace JSON must decode to an object")
        return cls.from_dict(data)


@dataclass(slots=True)
class EvaluationResult:
    """Result emitted by a single evaluator."""

    evaluator_name: str
    score: float
    passed: bool
    summary: str
    findings: list[str] = field(default_factory=list)
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.evaluator_name.strip():
            raise ValueError("evaluator_name must not be empty")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("score must be between 0.0 and 1.0")
        if not self.summary.strip():
            raise ValueError("summary must not be empty")
        _validate_string_list(self.findings, field_name="findings")
        _validate_json_value(self.metadata, path="metadata")

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluator_name": self.evaluator_name,
            "score": self.score,
            "passed": self.passed,
            "summary": self.summary,
            "findings": list(self.findings),
            "metadata": dict(self.metadata),
        }

    def to_json(self, *, indent: int | None = None) -> str:
        return json.dumps(
            self.to_dict(),
            indent=indent,
            sort_keys=True,
            allow_nan=False,
        )
