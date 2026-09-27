# Contributing to AgentAudit

Thank you for helping improve AgentAudit.

## Development setup

1. Fork and clone the repository.
2. Create a virtual environment with Python 3.10 or newer.
3. Install development dependencies with `python -m pip install -e ".[dev]"`.
4. Create a focused branch for your change.

Before opening a pull request, run:

```bash
ruff check .
mypy src examples
pytest --cov=agentaudit --cov-report=term-missing --cov-fail-under=85
python -m build
```

## Design expectations

- Keep the core framework- and model-provider-agnostic.
- Prefer deterministic evaluation when a rule can be expressed deterministically.
- Preserve JSON serialisability for trace data.
- Add full type hints to production code.
- Add or update tests for every behavioural change.
- Avoid new runtime dependencies unless there is a clear, documented benefit.
- Do not include API keys, secrets, proprietary datasets, or confidential traces.

## Pull requests

Keep pull requests small enough to review. Describe the problem, the chosen approach, tests performed, and any backwards-compatibility implications.

## Commit messages

Use concise imperative commit messages, for example:

```text
Add deterministic tool sequence evaluator
```
