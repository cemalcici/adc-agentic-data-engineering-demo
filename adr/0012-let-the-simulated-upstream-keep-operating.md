# Let the simulated upstream keep operating

## Status

Accepted, supersedes ADR-0005

## Date

2026-08-18

## Supersedes

ADR-0005 (Generate seed data deterministically from a one-shot service)

## Context and Problem Statement

The source dataset was seeded once and then never changed. Every pipeline run
therefore processed an identical table, and nothing on screen moved between
runs. For a demo whose argument is that a *living* pipeline broke and something
noticed, a frozen source undercuts the story before the failure is even
introduced.

The obvious way to add movement — loading incrementally rather than replacing —
turns out to be incompatible with the failure the demo is built on, for reasons
recorded in ADR-0010. So movement has to come from the source itself: the
upstream system continues to operate, and the pipeline keeps picking up what it
produces.

That reopens what ADR-0005 settled. It committed to a dataset byte-identical on
every cold start, chosen so that a row count quoted while rehearsing would still
be true while presenting. A source that grows cannot honour that unconditionally.

## Considered Options

- New records arrive on a fixed interval, generated from the same seed, with
  each record's values a pure function of its identifier
- Keep the source frozen and accept that nothing changes between runs
- Let arrivals be genuinely random, giving up reproducibility

## Decision Outcome

Chosen option: "Deterministic arrivals on a fixed interval", because it buys
movement without giving up what ADR-0005 was actually protecting. Making a
record's values depend on its identifier rather than on how many records came
before it means any record can be produced independently, so the initial seed and
every later arrival follow one rule and the source's contents are fully
determined by how many intervals have elapsed.

The guarantee changes shape rather than disappearing: reproducible at equal
elapsed intervals, instead of identical always. That is weaker, and it is why
this supersedes ADR-0005 rather than sitting alongside it — a reader walking the
graph should find the current commitment in one place, not have to reconcile two.

Random arrivals were rejected outright: a demo that cannot be rehearsed against
what it will actually show is worse than a static one. Keeping the source frozen
was rejected because the cost it avoids is small and the thing it gives up —
visible motion in a live demo — is most of why the pipeline is on screen at all.

## Consequences

- Good, because the row count moves between pipeline runs, so the demo shows a
  pipeline doing work rather than repeating itself.
- Good, because one generation rule now covers both the initial dataset and every
  arrival, so there is a single thing to reason about.
- Good, because the readiness check can still assert exactly: a legitimate count
  is the seeded figure plus a whole number of batches, and anything else is a
  real failure rather than expected drift.
- Bad, because reproducibility now depends on elapsed time. A rehearsal and a
  performance agree only if both have run for the same number of intervals, which
  is a condition someone has to remember.
- Bad, because the initial rows' values change as a result of the refactor. No
  behaviour depends on them, but the checksum recorded during CH1 no longer
  matches and anyone comparing against it will be briefly confused.
- Bad, because the source now has three writers across the project — the seeder,
  this component, and the drift script that follows — and nothing structurally
  stops them contending. They are separated by convention and by disjoint
  identifier ranges, not by mechanism.
