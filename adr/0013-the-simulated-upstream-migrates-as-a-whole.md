# The simulated upstream migrates as a whole

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

The demo turns on an upstream system renaming a column. Until now that rename
was understood as something done *to* the source table, and nothing else about
the simulated upstream was expected to react.

That assumption does not survive contact with the running system. The component
that keeps adding customer records names the columns it writes, so the moment the
rename lands it raises an undefined-column error. Because the service restarts on
failure, it then raises again, and again. Measured directly: the container cycled
back to a few seconds of uptime repeatedly for as long as the source stayed
renamed.

The window that matters is exactly the one this would run through. The demo's
centrepiece is an operator reading a diagnosis and deciding whether to approve a
fix, which takes as long as a person takes. A component failing on a loop in the
background for that entire stretch is not a detail.

## Considered Options

- Have the arrivals component read the identifier's name from the source at run
  time, so it follows the rename
- Detect the mismatch and pause cleanly until the shape matches again
- Have the drift trigger stop the arrivals service and start it again afterwards

## Decision Outcome

Chosen option: "Follow the rename", because it is what a real upstream system
does. A rename is that system migrating its own schema, and its own writers
migrate with it. Anything else simulates a different and stranger situation: a
system that renamed a column and simultaneously broke its own ingestion.

The identifier is found through the table's primary key rather than by position.
Position is an accident of how a table was written; the primary key is a
statement about what identifies a record, and that is what the writer actually
needs to know.

Pausing cleanly would have removed the crash loop with less code, but it freezes
the source for the length of the incident and gives up the moment where a
repaired pipeline catches up on everything that arrived while it was broken.
Having the drift trigger manage the arrivals service was rejected outright: that
trigger is scoped to touching the source and nothing else, and orchestrating
another service is not touching the source.

## Consequences

- Good, because nothing visibly fails during the incident except the pipeline,
  which is the only thing the demo is claiming is broken.
- Good, because records keep arriving while the pipeline is down, so approving
  the fix produces a visible catch-up rather than a return to where things were.
- Good, because the same principle now holds on both sides of the boundary: the
  extract carries the upstream shape rather than asserting one, and so does the
  upstream's own writer.
- Bad, because after the rename the old field name exists nowhere in the source.
  Anything trying to work out what the field used to be called cannot learn it
  by looking there; it has to read the transformation model, which is where the
  expectation is actually written down.
- Bad, because two components now infer the source's shape independently and by
  different means — one by column list, one by primary key. Both are right for
  their purpose, and they would diverge if the source ever gained a compound key.
