# Changelog

All notable changes to AgentAudit will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added the `Evidence` provenance model with strict JSON-compatible content and metadata.
- Extended `Scenario` with approval, latency, failure/retry, and evidence policy fields.
- Extended `TraceStep` with evidence references, approval linkage, and structured error/retry fields.
- Extended `Trace` with evidence storage and helper properties.
- Added deterministic `TraceIntegrityEvaluator` for cross-record trace invariants.
- Added v0.2 model serialisation and trace-integrity regression tests.
- Added deterministic `HumanApprovalEvaluator` with protected-tool, matching-ID, denial, and ordering checks.
- Added public approval action constants for requested, granted, and denied events.
- Added human-approval regression tests for valid, missing, late, denied, mismatched, and run-wide approval policies.

### Documentation

- Added a concrete Milestone 2 governance and reliability specification.
- Added the proposed v0.2 public API contract.
- Updated the README to show the first Milestone 2 implementation slice.
- Documented deterministic human-approval semantics and marked Issue #2 implemented.

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
