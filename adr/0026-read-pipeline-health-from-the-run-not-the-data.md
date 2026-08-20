# Read pipeline health from the run, not the data

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

The operator's console has to answer one question before any other: is the
pipeline working? There are three places it could ask, and they do not agree.

The warehouse is the tempting one, because it is right there and because
"is there data?" sounds like the same question. It is not. A failed run leaves
the previous mart in place — ADR-0008's structure means the transformation fails
at the staging view and the mart is reported as skipped rather than rebuilt — so
the warehouse keeps answering queries with the last good run's rows for as long
as the pipeline stays broken. Something reading it would report health through
the entire incident.

That is not a small inaccuracy. Silent pipeline failure, where the data looks
fine and nobody notices, is the problem the accompanying report opens with. A
console that inferred health from data would be a working demonstration of that
failure, running inside the demo built to argue against it.

The second option is to let the agent publish pipeline status into the incident
record, so the console reads one source. The third is the orchestrator's own
API, which is where the agent itself looks.

## Considered Options

- Read the latest run's status from the orchestrator's API
- Have the agent write pipeline status into the incident record for the console
  to read
- Infer health from the warehouse's contents

## Decision Outcome

Chosen option: "Read the latest run's status from the orchestrator", because it
is the only source that is both correct during a failure and independent of the
agent.

Correct during a failure rules out the warehouse entirely. Independent of the
agent rules out the second option: ADR-0015 made the two sides work when the
other does not, and a console whose health signal came from the agent would show
a confident stale green whenever the agent stopped — failing in exactly the
manner this decision exists to avoid, one component further along.

Reading the orchestrator's own database tables was not considered seriously.
They are its internals rather than its interface, they change between versions,
and ADR-0001 drew these boundaries so components talk through contracts.

## Consequences

- Good, because the console tells the truth during a failure, which is when
  telling the truth matters.
- Good, because health survives the agent being stopped, restarted, or never
  started.
- Good, because the console and the agent read the same source, so they cannot
  disagree about whether the pipeline is working.
- Bad, because the console needs its own orchestrator credential and a small
  client of its own, duplicating a little of the agent's.
- Bad, because health now depends on the orchestrator's API being reachable. If
  it is down the console cannot report health at all — which is honest, but it
  is a dependency the warehouse-reading option would not have had.
