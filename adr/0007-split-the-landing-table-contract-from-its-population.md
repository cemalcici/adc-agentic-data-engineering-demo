# Split the landing table contract from its population

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

ADR-0001 put the source and the warehouse in separate databases, so the
transformation layer cannot read the source directly. Its input has to arrive in
the warehouse first, in a landing table filled by an extract step.

That extract belongs to a later change, which leaves the transformation layer
being written before anything that feeds it exists. Either the transformation
waits — leaving a change that cannot verify its own work — or the dependency is
split so the part the transformation needs can be settled first.

There is also a mechanical constraint. In dbt a table is either a seed, which
dbt creates and owns, or a source, which dbt declares as existing and someone
else owns. The two cannot both apply to one table, so this choice determines
whether the models survive the arrival of a real extract unchanged.

## Considered Options

- Declare the landing table as a source; the transformation owns its contract,
  a later change owns filling it, and a fixture stands in for verification
- Define the landing table as a dbt seed configured to land on the same name
- Leave the landing table entirely to the change that builds the extract

## Decision Outcome

Chosen option: "Declare it as a source with a separate fixture", because it is
the only option under which the models never change when the real extract
arrives. A source declaration says what the transformation depends on without
claiming to produce it, which is exactly the relationship that holds.

The seed variant would work — dbt can be configured to write a seed to a chosen
schema and name — but it puts the origin of the data in configuration rather
than in the open, and leaves a seed in the project that would silently overwrite
real landing data if anyone ever ran it. Deferring the landing table entirely
would leave the transformation unverifiable, which the project's own workflow
rules forbid.

## Consequences

- Good, because the transformation layer can be built and verified before the
  orchestrator exists, keeping each unit independently provable.
- Good, because the extract has a written contract to satisfy rather than a
  shape inferred from whatever happens to exist.
- Good, because the models are unaffected when the fixture stops being what
  fills the table.
- Bad, because two things now write the same table at different times, and they
  can disagree. The source declaration is authoritative; the extract must be
  written against it rather than against whatever the fixture created.
- Bad, because a fixture that exists only for verification can be mistaken for a
  seeding mechanism. It must never run as part of a pipeline.
