# The drift trigger cannot undo itself

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

The trigger that introduces the upstream schema change is run during a live
demo, and the demo is rehearsed repeatedly before it is performed. The obvious
convenience is a way to put the column back, so a rehearsal can be repeated
without tearing the stack down.

The obvious convenience is unsafe here, and not for a reason care can fix.

ADR-0003 deliberately withholds the transformation project from this service.
That is what makes the write-scope invariant real rather than a convention. The
consequence is that the trigger cannot see whether the model has already been
repaired.

## Considered Options

- The trigger only introduces the change; resetting is a full teardown
- The trigger offers a reversal, documented as safe only before a fix is applied
- The trigger toggles the column's name based on its current state

## Decision Outcome

Chosen option: "No reversal", because a reversal that cannot check for the
condition that makes it dangerous should not exist.

Once the agent has rewritten the model to read the new field name, reversing the
source does not return the system to its starting state. The model expects the
new name, the source goes back to the old one, and the pipeline breaks again in
mirror image — a failure that resembles the original closely and has the opposite
cause. Diagnosing that is materially harder than diagnosing the failure the demo
is built around, and it would happen at the worst possible moment.

Documenting the restriction was considered and rejected: a flag that is safe
before one step and harmful after it, on a command run live in front of an
audience, will eventually be used at the wrong time. A toggle is worse still —
running the same command twice would silently repair the system, which is
precisely what the demo exists to show being done deliberately.

Reset is a full teardown of the stack plus discarding whatever the agent wrote
under the transformation project. Total, unambiguous, and already the documented
way the stack is reset.

## Consequences

- Good, because there is no path from this command to a confusing mirror-image
  failure.
- Good, because the trigger stays honest about its scope: it makes one change to
  the source and knows nothing else.
- Good, because reset means the same thing everywhere — a teardown — rather than
  having a partial reset that covers some state and not the rest.
- Bad, because every rehearsal repetition costs a teardown and a cold start, plus
  the wait for a first scheduled run. Rehearsing is slower than it would be with
  a reversal.
- Bad, because an operator who renames the column by hand still has every way to
  create the mirror-image failure. This decision removes the invitation, not the
  possibility.
