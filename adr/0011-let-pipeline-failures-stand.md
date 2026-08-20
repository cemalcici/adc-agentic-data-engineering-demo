# Let pipeline failures stand

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

The pipeline exists to fail in a specific way and have something notice. What
the orchestrator does between the failure happening and something acting on it
therefore shapes what that observer can see.

Retries are the default expectation for scheduled pipelines, and for good
reason: most pipeline failures are transient. The failure this system is built
around is not. A column that is absent because it was renamed upstream is still
absent a minute later, and no number of attempts will change that.

## Considered Options

- No retries on any task; a failed run stays failed until something acts on it
- Retries on extraction only, where transient failures are conceivable
- Retries on both tasks, as a conventional pipeline would have

## Decision Outcome

Chosen option: "No retries", because retrying a deterministic failure costs
twice and buys nothing. It delays the point at which the failure becomes
visible, and it introduces an intermediate retry state that any observer must
learn to interpret before it can conclude that something is actually wrong.
Failing once and staying failed gives that observer an unambiguous signal.

Retrying extraction alone is the more defensible real-world pattern —
transient failures are plausible where a network and a database are involved,
and not plausible where a column is missing. It was rejected because in this
stack the database is local and every dependent service already waits on its
health, so it would be a mechanism guarding a failure mode that does not occur
here.

Runs do not overlap, and a first start does not replay intervals from before the
pipeline existed. Both follow from the same intent: what an observer sees should
be the current state of the pipeline, not an artefact of the orchestrator
catching up with itself.

## Consequences

- Good, because a failure is visible at once, in one state, attributed to the
  task that caused it.
- Good, because anything watching for failure has a single condition to detect
  rather than a state machine to interpret.
- Good, because a failed run stays on the record instead of being replaced by a
  successful retry, so the history of what went wrong survives.
- Bad, because a genuinely transient failure — a restart mid-run, say — surfaces
  as a real failure and would be diagnosed as one. In a system that acts on
  failures automatically, that is a false positive waiting to happen.
- Bad, because this is not how a production pipeline should be configured, and
  anyone reading this deployment as a template would take the wrong lesson from
  it.
- Bad, because failed runs accumulate while a fault persists, at one per
  scheduled interval. Readable at the demo's cadence, and noise at any other.
