"""Deterministic execution-failure and retry-policy evaluator."""

from __future__ import annotations

from collections import defaultdict

from agentaudit.models import EvaluationResult, JSONValue, Scenario, Trace, TraceStep


class ExecutionFailureEvaluator:
    """Evaluate structured execution errors and explicit retry attempts."""

    @property
    def name(self) -> str:
        return "execution_failure"

    def evaluate(self, scenario: Scenario, trace: Trace) -> EvaluationResult:
        findings: list[str] = []
        error_steps = trace.error_steps

        if len(error_steps) > scenario.max_errors:
            findings.append(
                "Error count exceeded policy: "
                f"{len(error_steps)} > {scenario.max_errors}"
            )

        unexpected_errors: list[JSONValue] = []
        if scenario.allowed_error_types:
            allowed = set(scenario.allowed_error_types)
            for index, step in enumerate(trace.steps, start=1):
                if step.error is None:
                    continue
                if step.error_type not in allowed:
                    unexpected_errors.append(
                        {
                            "step": index,
                            "error_type": step.error_type,
                        }
                    )

        if unexpected_errors:
            rendered = ", ".join(
                f"step {item['step']} ({item['error_type']!r})"
                for item in unexpected_errors
                if isinstance(item, dict)
            )
            findings.append(f"Unexpected error types: {rendered}")

        retry_findings, retry_metadata = self._evaluate_retries(scenario, trace)
        findings.extend(retry_findings)

        checks_total = 2 + int(scenario.max_retries_per_tool is not None)
        checks_passed = checks_total - (
            int(len(error_steps) > scenario.max_errors)
            + int(bool(unexpected_errors))
            + int(bool(retry_findings) and scenario.max_retries_per_tool is not None)
        )

        # Retry structure is always validated, even when no retry limit is configured.
        if retry_findings and scenario.max_retries_per_tool is None:
            checks_total += 1
        elif scenario.max_retries_per_tool is None:
            checks_total += 1
            checks_passed += 1

        passed = not findings
        score = checks_passed / checks_total if checks_total else 1.0

        metadata: dict[str, JSONValue] = {
            "error_count": len(error_steps),
            "max_errors": scenario.max_errors,
            "allowed_error_types": list(scenario.allowed_error_types),
            "unexpected_errors": unexpected_errors,
            "checks_total": checks_total,
            "checks_passed": checks_passed,
            **retry_metadata,
        }

        return EvaluationResult(
            evaluator_name=self.name,
            score=score,
            passed=passed,
            summary=(
                "Execution failure and retry checks passed."
                if passed
                else "Execution failure and retry checks failed."
            ),
            findings=findings,
            metadata=metadata,
        )

    def _evaluate_retries(
        self,
        scenario: Scenario,
        trace: Trace,
    ) -> tuple[list[str], dict[str, JSONValue]]:
        findings: list[str] = []
        calls_by_tool: dict[str, list[tuple[int, TraceStep]]] = defaultdict(list)

        for index, step in enumerate(trace.steps, start=1):
            if step.action_type == "tool_call" and step.tool_name is not None:
                calls_by_tool[step.tool_name].append((index, step))

        retries_by_tool: dict[str, JSONValue] = {}
        malformed_attempts: list[JSONValue] = []
        retry_policy_violations: list[JSONValue] = []
        retry_limit_violations: list[JSONValue] = []

        for tool_name, calls in calls_by_tool.items():
            explicit = [(index, step) for index, step in calls if step.attempt is not None]
            if not explicit:
                retries_by_tool[tool_name] = 0
                continue

            retry_count = sum(
                1 for _, step in explicit if step.attempt is not None and step.attempt > 1
            )
            retries_by_tool[tool_name] = retry_count

            previous_explicit: tuple[int, TraceStep] | None = None
            for index, step in explicit:
                attempt = step.attempt
                if attempt is None:
                    continue

                if attempt < 1:
                    malformed_attempts.append(
                        {"step": index, "tool_name": tool_name, "attempt": attempt}
                    )
                    previous_explicit = (index, step)
                    continue

                if previous_explicit is None:
                    if attempt != 1:
                        malformed_attempts.append(
                            {"step": index, "tool_name": tool_name, "attempt": attempt}
                        )
                    previous_explicit = (index, step)
                    continue

                previous_index, previous = previous_explicit
                expected_attempt = (
                    previous.attempt + 1 if previous.attempt is not None else None
                )
                if attempt != expected_attempt:
                    malformed_attempts.append(
                        {"step": index, "tool_name": tool_name, "attempt": attempt}
                    )
                elif attempt > 1 and (
                    previous.error is None or previous.retryable is not True
                ):
                    retry_policy_violations.append(
                        {
                            "step": index,
                            "tool_name": tool_name,
                            "attempt": attempt,
                            "previous_step": previous_index,
                            "previous_had_error": previous.error is not None,
                            "previous_retryable": previous.retryable,
                        }
                    )

                previous_explicit = (index, step)

            if (
                scenario.max_retries_per_tool is not None
                and retry_count > scenario.max_retries_per_tool
            ):
                retry_limit_violations.append(
                    {
                        "tool_name": tool_name,
                        "retries": retry_count,
                        "limit": scenario.max_retries_per_tool,
                    }
                )

        if malformed_attempts:
            rendered = ", ".join(
                f"step {item['step']} {item['tool_name']} (attempt={item['attempt']})"
                for item in malformed_attempts
                if isinstance(item, dict)
            )
            findings.append(f"Malformed retry attempts: {rendered}")

        if retry_policy_violations:
            rendered = ", ".join(
                f"step {item['step']} {item['tool_name']} (attempt={item['attempt']})"
                for item in retry_policy_violations
                if isinstance(item, dict)
            )
            findings.append(
                "Retry attempted without a retryable preceding error: "
                f"{rendered}"
            )

        if retry_limit_violations:
            rendered = ", ".join(
                (
                    f"{item['tool_name']} "
                    f"({item['retries']} retries > {item['limit']})"
                )
                for item in retry_limit_violations
                if isinstance(item, dict)
            )
            findings.append(f"Retry limit exceeded: {rendered}")

        metadata: dict[str, JSONValue] = {
            "retries_by_tool": retries_by_tool,
            "malformed_attempts": malformed_attempts,
            "retry_policy_violations": retry_policy_violations,
            "retry_limit_violations": retry_limit_violations,
            "max_retries_per_tool": scenario.max_retries_per_tool,
        }
        return findings, metadata
