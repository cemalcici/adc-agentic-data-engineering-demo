# Reach tools through direct clients rather than MCP

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

The agent has to reach three things outside itself: the orchestrator's API, the
warehouse, and the transformation project on disk. The accompanying report
treats the Model Context Protocol as the emerging standard for exactly this, and
names it among the reasons agentic systems became practical when they did.

Using it here would be defensible and would match what the report describes.
The question is whether it earns its cost in a single-agent proof of concept
where every dependency runs in the same Compose network.

## Considered Options

- Call each system through an ordinary client library, exposed to the graph as
  tool functions
- Run an MCP server in front of each system and have the agent speak MCP
- Use MCP for the orchestrator, where a server already exists, and direct
  clients elsewhere

## Decision Outcome

Chosen option: "Direct clients", because what MCP provides is not what this
system is short of. Its value is a uniform, governed surface across many tools
and many agents — discovery, permissioning, and a common protocol worth having
when the alternative is bespoke integrations multiplying. Here there is one
agent, three dependencies, and no discovery problem: the agent knows exactly
what it needs and where it is.

Against that, MCP would add a server per dependency to the topology, each with
its own configuration, health, and failure mode, on a stack already carrying
eight services. The demo would spend attention on plumbing rather than on the
loop it exists to show.

The mixed option was rejected as the worst of both: the operational cost of
running a server plus the inconsistency of two integration styles in one agent.

This is a scope decision, not a judgement about MCP. The graph's structure does
not depend on how its tools are reached, so swapping these clients for MCP
servers later would leave the nodes untouched — which is what makes it a
reasonable thing to defer.

## Consequences

- Good, because the agent has no infrastructure between it and its dependencies,
  so a failure is in the agent or in the dependency and nowhere else.
- Good, because the demo machine carries three fewer services.
- Good, because the swap remains available: tools are function-shaped, and MCP
  tools are too.
- Bad, because the demo does not show a capability the accompanying report
  presents as central to why this is possible now. Anyone asking "why not MCP?"
  deserves this ADR as the answer, and the question should be expected.
- Bad, because access control is whatever each client is configured with, rather
  than something a protocol layer could express and enforce uniformly. At one
  agent and one operator that is acceptable; it would not be at scale.
