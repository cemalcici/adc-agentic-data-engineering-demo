# Generate seed data deterministically from a one-shot service

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

The demo hinges on a believable upstream table breaking, so the source dataset
has to look like real customer data rather than a fixture — which argues for
volume. But the demo is rehearsed and then performed, sometimes on a different
machine, and any figure quoted during rehearsal has to still be true on stage —
which argues for reproducibility. Volume and reproducibility are usually in
tension: hand-written rows are reproducible but small, generated rows are
plentiful but vary per run.

There is also a placement constraint. The official PostgreSQL image runs only
shell and SQL files from its initialisation directory and has no Python
interpreter, so a generator cannot simply be dropped in beside the schema
definitions.

## Considered Options

- A one-shot service that runs the generator with a fixed random seed at startup
  and bulk-loads the result, then exits
- Commit the generator and the data it produces, with database initialisation
  loading the committed file
- Seed through the orchestrator as a dedicated pipeline

## Decision Outcome

Chosen option: "One-shot service with a fixed random seed", because it resolves
the tension rather than trading one side away: a fixed seed makes generated data
reproducible, so the dataset can be both large and identical across runs.
Running it as a service means the generator actually executes during a cold
start — it is part of the system rather than a build artifact — and its
completion becomes something later services can depend on.

Committing generated output was rejected because the generator would become
decorative, never running in the system it seeds, and the repository would carry
a bulky generated file. Seeding through the orchestrator was rejected as a
boundary violation: it takes database initialisation away from the component that
owns it and widens the orchestrator's responsibility beyond the pipeline it
exists to run.

### Consequences

- Good, because the dataset has credible volume and is byte-identical on every
  cold start, so rehearsal figures hold during the performance.
- Good, because seeding is an explicit, observable step with a completion signal
  that dependent services can wait on, rather than an invisible side effect of
  container startup.
- Bad, because cold start now includes generation and bulk-load time.
- Bad, because "deterministic" only holds while the generator's logic is
  unchanged; editing it silently produces a different dataset that is still
  perfectly reproducible.
- Follow-up: the expected row count must be asserted by the readiness check, so
  that a changed generator fails loudly instead of quietly altering what the
  demo shows.
