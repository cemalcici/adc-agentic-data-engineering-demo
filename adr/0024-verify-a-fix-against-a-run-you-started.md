# Verify a fix against a run you started

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

Once an approved fix is written, something has to decide whether it worked. The
pipeline runs on a schedule and its failures stand (ADR-0011), so there is
usually a run in flight or about to be, and the obvious economy is to let the
next one that finishes answer the question.

That economy is a trap. A run already in progress may have started before the
file was written, and its outcome describes a version of the project it never
read. If it fails, the fix is blamed for a failure it had no part in; if it
passes, the fix is credited with a success it did not cause. Either way the
incident's outcome is a statement about the wrong thing.

The demo's entire argument rests on the final state being trustworthy. "The
pipeline is green because the agent's fix was approved and applied" is the
sentence the audience is asked to believe, and it is only true if the green run
is one that read the fix.

## Considered Options

- Trigger unconditionally after writing, record the returned run identifier, and
  judge the fix by that run alone
- Adopt whichever run is currently in flight, or the next one to finish
- Pause the schedule, verify in isolation, then resume

## Decision Outcome

Chosen option: "Trigger and judge only the run you started", because it is the
only option where the outcome is about the fix.

The orchestrator returns an identifier for the run it starts, and that
identifier is recorded on the incident, kept apart from the run that originally
failed. Everything afterwards reads that one run. Because the pipeline permits a
single active run, a trigger issued while another run is going queues instead of
conflicting — the orchestrator serialises, and watching one identifier means the
agent never has to reason about the queue.

Adopting an in-flight run was rejected because it saves seconds of pipeline time
and spends the meaning of the result. Pausing the schedule was rejected on
authority rather than mechanism: it works, but it gives a component whose write
scope is deliberately a single directory the ability to stop the pipeline
entirely, which is a far larger power than the one being granted.

## Consequences

- Good, because a recorded outcome is always a statement about the fix that was
  applied, and never about a run that predates it.
- Good, because the run being watched is named on the incident, so "this broke on
  run A and was confirmed fixed on run D" is answerable from the record.
- Good, because the agent needs no view of the orchestrator's queue; one
  identifier is the whole of what it tracks.
- Bad, because a redundant pipeline run may execute — the scheduled one that was
  already going, plus the one triggered for verification.
- Bad, because a crash between triggering and recording the identifier leaves a
  run nobody is watching, and the next pass will trigger another. The
  consequence is a spare run rather than a wrong answer, but it is a window.
