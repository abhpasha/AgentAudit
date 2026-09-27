# Milestone 2 — Governance and Reliability Primitives

Milestone 2 targets **AgentAudit v0.2.0**. Its purpose is to deepen the framework-agnostic core before any LangChain, LangGraph, MCP, model-provider, or LLM-as-judge integration is added.

## Goals

AgentAudit v0.2 should deterministically answer:

- Was required human approval obtained before a protected action?
- Did the run stay within configured latency budgets?
- Were execution errors and retries within policy?
- Is the trace internally consistent?
- Can the final output be traced to declared evidence?
- Can multiple scenarios be executed and aggregated as a regression suite?

## Scope

### 1. Trace integrity

Add a `TraceIntegrityEvaluator` that validates cross-record invariants that cannot be safely checked inside one dataclass alone.

Checks should include:

- `trace.scenario_name == scenario.name`
- evidence IDs are unique
- every referenced evidence ID resolves
- step timestamps are non-decreasing
- steps fall within `started_at` and `finished_at`
- `tool_call` steps include `tool_name`
- approval events include `approval_id`
- retry attempt numbers are >= 1
- `error_type` is not set without an error

### 2. Human approval

Make the existing `Scenario.requires_human_approval` field operational and add protected-action configuration.

Standard action types:

- `human_approval_requested`
- `human_approval_granted`
- `human_approval_denied`

`HumanApprovalEvaluator` should verify that approval is granted before protected actions, request/grant IDs match, denied approvals are not treated as grants, and protected execution does not continue after denial.

### 3. Latency budgets

Add scenario policy fields for:

- total trace latency
- maximum step latency
- per-tool latency limits

`LatencyEvaluator` should evaluate configured budgets deterministically. Missing measurements must be reported explicitly; missing latency must never be interpreted as zero.

### 4. Execution failures and retries

Use the existing `TraceStep.error` field and add structured failure information such as `error_type`, `retryable`, and `attempt`.

`ExecutionFailureEvaluator` should check:

- total error count
- allowed error types
- retry limits
- valid retry attempt numbers
- retry policy compliance

Duplicate tool calls alone are not automatically retries. Explicit attempt metadata is authoritative.

### 5. Evidence grounding

Introduce a first-class `Evidence` model and evidence references from trace steps.

The deterministic v0.2 grounding layer should verify provenance only:

- required evidence sources are present
- forbidden evidence sources are absent
- evidence references resolve
- minimum evidence requirements are satisfied
- final output references evidence when required

v0.2 must **not** claim semantic entailment or factual truth from natural-language outputs. LLM-based judging remains out of scope.

### 6. Evaluation suites

Add:

- `EvaluationSuite`
- `ScenarioEvaluation`
- `SuiteResult`
- `run_evaluation(...)`
- `evaluate_suite(...)`

Keep the existing `evaluate(agent, scenario)` API backwards compatible.

Default aggregation:

- scenario passes when all evaluator results pass
- scenario score is the mean evaluator score
- suite passes when all scenarios pass
- suite score is the mean scenario score

Weighted scoring is intentionally deferred.

## Proposed implementation order

1. Extend core models and JSON serialisation.
2. Implement `TraceIntegrityEvaluator`.
3. Implement `HumanApprovalEvaluator`.
4. Implement `LatencyEvaluator`.
5. Implement `ExecutionFailureEvaluator`.
6. Implement `EvidenceGroundingEvaluator`.
7. Implement suite orchestration and richer result objects.
8. Update public exports, examples, README, changelog, and tests.
9. Verify CI on Python 3.10–3.13.

## Test acceptance criteria

Milestone 2 must add deterministic tests for:

- approval granted before action
- missing approval
- approval after protected action
- denied approval
- mismatched approval IDs
- total latency within/exceeding budget
- step latency within/exceeding budget
- per-tool latency limits
- missing latency measurements
- no errors
- permitted and unexpected error types
- successful retry
- retry limit exceeded
- valid and broken evidence references
- required and forbidden evidence sources
- final output grounding requirement
- duplicate evidence IDs
- trace ordering/integrity failures
- all-pass suite
- partially failing suite
- deterministic suite aggregation

Existing v0.1 tests must continue to pass.

## Definition of done

Milestone 2 is complete when:

- the core remains framework-agnostic
- runtime dependencies remain zero unless a strong reason is documented
- all public models remain JSON-serialisable
- the new evaluators are deterministic
- `evaluate(...)` remains backwards compatible
- Ruff passes
- strict mypy passes
- pytest passes with >=85% branch-aware coverage
- Python 3.10, 3.11, 3.12, and 3.13 CI are green
- no LangChain, LangGraph, MCP, OpenAI, LLM-as-judge, HTML reporting, benchmark dataset, or multi-agent integration is added
