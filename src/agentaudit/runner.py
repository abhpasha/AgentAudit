"""Runner abstractions for framework-agnostic agent execution."""

from __future__ import annotations

from typing import Protocol

from .models import Scenario, Trace


class Agent(Protocol):
    """Minimal contract required by the built-in runner."""

    def run(self, scenario: Scenario) -> Trace:
        """Execute a scenario and return its trace."""
        ...


class Runner(Protocol):
    """Execution boundary that future framework adapters can implement."""

    def run(self, agent: Agent, scenario: Scenario) -> Trace:
        """Execute an agent for a scenario and return a trace."""
        ...


class BasicRunner:
    """Run agents that directly implement the Agent protocol."""

    def run(self, agent: Agent, scenario: Scenario) -> Trace:
        trace = agent.run(scenario)
        if not isinstance(trace, Trace):
            raise TypeError("Agent.run() must return an agentaudit.Trace")
        if trace.scenario_name != scenario.name:
            raise ValueError(
                "Trace scenario_name must match the Scenario name "
                f"({trace.scenario_name!r} != {scenario.name!r})"
            )
        return trace
