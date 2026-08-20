# Prove a fix by building it on a copy

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

The agent proposes a corrected transformation and an operator decides whether to
apply it. A proposal that is approved and then fails is worse than no proposal:
it spends the operator's trust, leaves the pipeline broken, and teaches an
audience that the approval step is decoration.

So a candidate should be checked before anyone sees it. Two things make that
harder than it sounds.

ADR-0008 established that parsing is not enough. The staging layer is a view,
and a view that reads a column which does not exist parses perfectly well and
fails when it is created — which is the entire error class this system exists to
catch.

And the agent has no way to build anything. ADR-0009 put dbt in the
orchestrator's image, in an isolated virtualenv. The agent runs in a different
container and was measured to have no dbt at all.

## Considered Options

- Build the whole project on a copy, inside the agent, with dbt installed there
  too from the same pinned versions the pipeline uses
- Have the orchestrator validate, through a pipeline whose purpose is to check a
  candidate
- Give the agent the container runtime's socket so it can use the orchestrator's
  existing dbt

## Decision Outcome

Chosen option: "Build the whole project on a copy, inside the agent", because it
is the only option where validation is both faithful and contained.

Faithful matters in three ways. Everything is built, not just the changed file,
because a correction that builds alone and breaks what depends on it is exactly
the case worth catching. It is built against the real landing table, because a
candidate proven against invented data has been proven against the wrong thing.
And it is built with the same dbt the pipeline runs, because a check using a
different build predicts a different outcome.

Contained matters because validation must not be distinguishable from running.
The copy is written to scratch space, never to the transformation project, and
the build writes into throwaway schemas that are dropped afterwards, so the
pipeline's own output is untouched.

The duplicate dbt installation is the cost, and its danger is drift: two
installations that diverge would make validation predict the wrong build. Both
images therefore install from one shared pinned requirements file — not as a
convention to remember, but as the only place either image gets its versions
from.

Validating through the orchestrator was rejected because it couples the agent's
inner loop to pipeline scheduling, puts a pipeline whose purpose is
agent-internal into the orchestrator, and introduces a second way to trigger
runs beside the one the next change needs. The container socket was rejected
outright: it would give a component whose write scope is deliberately one
directory the ability to do anything to any container, which empties ADR-0003 of
meaning.

## Consequences

- Good, because nothing reaches the operator that has not been proven to build,
  so approving a proposal cannot fail for a reason the agent could have found.
- Good, because validation exercises what the pipeline exercises, including the
  dependencies between transformations.
- Good, because the pipeline's output and the transformation project are
  provably untouched by validation.
- Bad, because dbt is now installed twice, and the agent's image is larger and
  slower to build for it.
- Bad, because the two installations must never diverge. The shared pin makes
  that structural, but a base image shifting a transitive dependency could still
  separate them in ways the pin does not cover.
- Bad, because building proves a candidate runs, not that it is correct. A
  correction that quietly produces wrong values would pass. That judgement stays
  with the operator, and this must not be mistaken for making the review
  optional.
- Follow-up: anyone changing dbt's version changes it in one file, for both
  images, and rebuilds both.
