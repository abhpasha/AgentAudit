# AgentAudit

AgentAudit is an open-source, framework-agnostic Python toolkit for evaluating and governing agentic AI systems. It is designed to test not only what an agent returns, but also **how the agent got there**: which tools it selected, the order in which tools were called, execution evidence, policy constraints, latency, failures, and other trace-level behaviour.

> **Status:** v0.1 is complete. Milestone 2 now includes core governance models plus deterministic trace-integrity, human-approval, and latency-budget evaluation.

## Problem statement

Traditional AI evaluation often focuses on the final text output. Agentic systems introduce a larger failure surface: an answer can look correct even when the agent called a forbidden data source, used tools in an unsafe order, exceeded an execution budget, or relied on evidence that should not have been used.

AgentAudit makes these behaviours explicit through three concepts:

1. **Scenarios** declare expected and forbidden behaviour.
2. **Traces** capture structured, JSON-serialisable execution evidence.
3. **Evaluators** deterministically compare traces against scenario constraints.

The core has no dependency on OpenAI, LangChain, LangGraph, or any other model or agent framework.

## Installation

AgentAudit requires Python 3.10 or newer.

For local development:

```bash
git clone https://github.com/abhpasha/AgentAudit.git
cd AgentAudit
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

When a release is published to PyPI, installation will be:

```bash
pip install agentaudit
```

## Quick start

```python
from datetime import UTC, datetime

from agentaudit import Scenario, Trace, TraceStep, evaluate


class InventoryAgent:
    def run(self, scenario: Scenario) -> Trace:
        now = datetime.now(UTC)
        return Trace(
            scenario_name=scenario.name,
            steps=[
                TraceStep(
                    timestamp=now,
                    actor="agent",
                    action_type="tool_call",
                    tool_name="inventory_lookup",
                    input={"sku": "ABC123"},
                    output={"in_stock": True},
                )
            ],
            started_at=now,
            finished_at=now,
        )


scenario = Scenario(
    name="stock_check",
    prompt="Check inventory for ABC123",
    expected_tools=["inventory_lookup"],
    forbidden_tools=["customer_database"],
    expected_tool_sequence=["inventory_lookup"],
    max_tool_calls=1,
)

results = evaluate(InventoryAgent(), scenario)
for result in results:
    print(result.evaluator_name, result.passed, result.score)
```

Run the complete example with:

```bash
python examples/simple_agent.py
```

## Architecture overview

```text
Scenario
   │
   ▼
 Runner ─── executes ───► Agent
   │                       │
   └──────── Trace ◄───────┘
              │
              ├── TraceStep[]
              └── Evidence[]
              │
              ▼
      deterministic evaluators
        │        │         │
        ▼        ▼         ▼
   Integrity  Selection  Sequence
        │        │         │
        └──── EvaluationResult
```

### Core models

- `Scenario` describes test inputs and behavioural/governance expectations.
- `Evidence` stores framework-neutral provenance with source, content, optional URI/hash, retrieval time, and metadata.
- `TraceStep` captures one timestamped action plus evidence references, approval linkage, and structured retry/error fields.
- `Trace` contains ordered steps, execution timing, evidence, and helper views for tools, errors, evidence, and final outputs.
- `EvaluationResult` is the stable output contract for evaluators.

### Execution boundary

`Runner` and `Agent` are Python protocols. The built-in `BasicRunner` works with any agent implementing `run(scenario) -> Trace`. Future integrations can implement `Runner` without changing the core models or evaluators.

### Deterministic evaluators

- `ToolSelectionEvaluator` checks expected tools, forbidden tools, and `max_tool_calls`.
- `ToolSequenceEvaluator` requires an exact ordered match when `expected_tool_sequence` is configured.
- `TraceIntegrityEvaluator` validates trace identity, ordering, time bounds, evidence references, tool-call structure, approval IDs, retry attempts, and structured errors.
- `HumanApprovalEvaluator` checks that protected tool calls are preceded by a matching request/grant pair and rejects late, denied, or mismatched approvals.
- `LatencyEvaluator` checks wall-clock, per-step, and per-tool latency budgets and reports missing latency observations explicitly.

`TraceIntegrityEvaluator` is available explicitly during the incremental v0.2 implementation. The default `evaluate(...)` evaluator set remains unchanged for v0.1 compatibility until the v0.2 orchestration work is complete.

Repeated calls are retained in the trace. They are reported by tool-selection evaluation but are not automatically failures: retries can be legitimate. They fail when they violate a declared sequence or call limit.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy src examples
pytest --cov=agentaudit --cov-report=term-missing --cov-fail-under=85
python -m build
```

## Roadmap

### Milestone 1 — v0.1 foundation ✅

- Core scenario and trace models
- JSON trace serialisation
- Runner protocols
- Deterministic tool-selection and tool-sequence evaluation
- Tests, packaging, CI, and project governance documents

### Milestone 2 — v0.2 governance and reliability 🚧

Implemented in the first v0.2 slice:

- `Evidence` provenance model
- governance policy fields on `Scenario`
- evidence/approval/failure/retry fields on `TraceStep`
- evidence storage and helper properties on `Trace`
- deterministic `TraceIntegrityEvaluator`
- deterministic `HumanApprovalEvaluator`
- deterministic `LatencyEvaluator`
- standard approval action constants for requested, granted, and denied events

Remaining Milestone 2 work:
- execution failure and retry evaluation
- evidence grounding evaluation
- reusable evaluation suites and richer result API

See [Milestone 2 specification](docs/MILESTONE_2.md) and the [proposed v0.2 API](docs/V0_2_API.md).

### Later milestones

- LangChain and LangGraph adapters
- MCP tracing integration
- LLM-as-judge evaluators
- HTML/reporting outputs
- Multi-agent tracing
- Benchmark datasets
- CLI workflows

These later features remain intentionally out of scope while the framework-agnostic core is still being stabilised.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

Please report security concerns according to [SECURITY.md](SECURITY.md), rather than opening a public issue for sensitive vulnerabilities.

## License

Apache-2.0. See [LICENSE](LICENSE).
