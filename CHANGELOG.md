# Changelog

All notable changes to AgentAudit will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-27

### Added

- Framework-agnostic `Scenario`, `TraceStep`, `Trace`, and `EvaluationResult` models.
- Strict JSON serialisation for execution traces and evaluation results.
- `Agent` and `Runner` protocols plus `BasicRunner`.
- Deterministic `ToolSelectionEvaluator` and `ToolSequenceEvaluator`.
- High-level `evaluate(agent, scenario)` public API.
- Unit test suite with coverage enforcement.
- Framework-free inventory agent example.
- Python packaging metadata for Python 3.10+.
- GitHub Actions CI for linting, type checking, tests, coverage, and package build.
- Contributor, security, code-of-conduct, and Apache-2.0 licensing documentation.
