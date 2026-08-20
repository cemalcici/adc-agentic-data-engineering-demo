# Transform through a staging view into a mart table

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

The transformation layer is where the demo's failure is staged: an upstream
column rename has to break it, visibly and diagnosably, so an agent can find the
cause and propose a fix. How many models exist, and how each is materialised,
decides what that failure looks like and how hard it is to locate.

`code-standards.md` called for a single model, on the grounds that a generated
diff should be easy to review on screen. That reasoning is sound but incomplete:
it optimises for the diff and ignores what the agent has to do before producing
one. A single-file project means the file to fix is known in advance, so the
demo never shows the agent working out *where* the problem is — which is the
part of root-cause analysis the accompanying report actually emphasises.

## Considered Options

- Two models: a staging view over the landing table, and a mart table built from
  it
- One model reading the landing table and producing the warehouse table directly
- Two models, both materialised as tables

## Decision Outcome

Chosen option: "A staging view into a mart table", because the materialisations
do real work here rather than being a stylistic choice.

PostgreSQL validates column references when a view is created, so a renamed
upstream column fails at view creation. The failure therefore lands in the
staging model — the layer closest to the change that caused it — and the mart is
reported as skipped rather than rebuilt from stale data. An agent reading that
output has to identify which model failed before it can fix anything, and it
gets an unambiguous answer.

The mart is a table because "the warehouse holds output" must be observable by
querying it; a view would satisfy the transformation without producing anything
durable to point at.

A single model was rejected for the reason above. Two tables were rejected
because a table materialisation would surface the same failure less precisely,
and because rebuilding the staging layer as a table buys nothing at this size.

This diverges from `code-standards.md`, which is updated to match rather than
left contradicting the code.

## Consequences

- Good, because the failure lands in a specific, named model, so diagnosis has
  something concrete to identify rather than a whole project to search.
- Good, because a skipped dependant is visible in the run output, which stops a
  later agent from concluding the mart was fine.
- Good, because the layered shape resembles a real project, which makes
  self-healing over it a stronger demonstration than repairing a single file.
- Bad, because the agent's writable target becomes a set of files rather than
  one. Whitelist validation must accept any model in the project while still
  refusing anything outside it, which is a weaker constraint than naming one
  file.
- Bad, because the agent must now select a file before fixing it, adding a way
  to be wrong that a single-model project did not have.
- Bad, because a staging view's errors appear only when it is built, not when
  the project is parsed. Any later validation of a proposed fix has to build
  against the database rather than parse the project.
