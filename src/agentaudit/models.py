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


@dataclass(slots=True)
class Scenario:
    """A deterministic description of expected agent behaviour."""

    name: str
    prompt: str
    expected_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    expected_tool_sequence: list[str] = field(default_factory=list)
    max_tool_calls: int | None = None
    requires_human_approval: bool = False
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Scenario name must not be empty")
        if not self.prompt.strip():
            raise ValueError("Scenario prompt must not be empty")

        _validate_string_list(self.expected_tools, field_name="expected_tools")
        _validate_string_list(self.forbidden_tools, field_name="forbidden_tools")
        _validate_string_list(
            self.expected_tool_sequence, field_name="expected_tool_sequence"
        )

        duplicate_expected = len(self.expected_tools) != len(set(self.expected_tools))
        duplicate_forbidden = len(self.forbidden_tools) != len(set(self.forbidden_tools))
        if duplicate_expected or duplicate_forbidden:
            raise ValueError("expected_tools and forbidden_tools must not contain duplicates")

        overlap = set(self.expected_tools) & set(self.forbidden_tools)
        if overlap:
            names = ", ".join(sorted(overlap))
            raise ValueError(f"Tools cannot be both expected and forbidden: {names}")

        if self.max_tool_calls is not None and self.max_tool_calls < 0:
            raise ValueError("max_tool_calls must be greater than or equal to zero")

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
        }

    def to_json(self, *, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, allow_nan=False)


@dataclass(slots=True)
class TraceStep:
    """One observable step in an agent execution trace."""

    timestamp: datetime
    actor: str
    action_type: str
    tool_name: str | None = None
    input: JSONValue = None
    output: JSONValue = None
    latency_ms: float | None = None
    error: str | None = None
    metadata: dict[str, JSONValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_datetime(self.timestamp, field_name="timestamp")
        if not self.actor.strip():
            raise ValueError("TraceStep actor must not be empty")
        if not self.action_type.strip():
            raise ValueError("TraceStep action_type must not be empty")
        if self.tool_name is not None and not self.tool_name.strip():
            raise ValueError("tool_name must be None or a non-empty string")
        if self.latency_ms is not None and self.latency_ms < 0:
            raise ValueError("latency_ms must be greater than or equal to zero")
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
        )


@dataclass(slots=True)
class Trace:
    """Complete, JSON-serialisable evidence from one scenario execution."""

    scenario_name: str
    steps: list[TraceStep]
    started_at: datetime
    finished_at: datetime
    metadata: dict[str, JSONValue] = field(default_factory=dict)

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "steps": [step.to_dict() for step in self.steps],
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def to_json(self, *, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, allow_nan=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Trace:
        return cls(
            scenario_name=data["scenario_name"],
            steps=[TraceStep.from_dict(step) for step in data.get("steps", [])],
            started_at=datetime.fromisoformat(data["started_at"]),
            finished_at=datetime.fromisoformat(data["finished_at"]),
            metadata=data.get("metadata", {}),
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
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, allow_nan=False)
