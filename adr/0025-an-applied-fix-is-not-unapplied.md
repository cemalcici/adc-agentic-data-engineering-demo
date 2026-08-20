# An applied fix is not unapplied

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

An approved fix can be written, the pipeline re-triggered, and the run can still
fail. The project is then left carrying a change that did not work, and the
tidy-looking response is for the agent to put the file back the way it found it.

That response is more dangerous than the mess it cleans up. The agent's
permission to write to the transformation project comes from one place: an
operator approved specific contents. A revert has no such approval behind it. It
would be the agent writing to the project on its own judgement — and doing so at
the exact moment something has already gone wrong, which is the worst moment for
a component to start acting unsupervised.

The write scope is enforced structurally (ADR-0003) precisely so that what the
agent may touch is not a matter of trusting its restraint. A self-initiated
revert would stay inside that scope and still walk around the gate, because the
gate is not about *where* the agent writes but about *whether a human said so*.

## Considered Options

- Leave the applied fix in place; the incident concludes and the operator
  restores the project if they want to
- Revert to the contents recorded before the change, automatically, on a failed
  verification
- Leave it in place but offer a separate reverting action the operator approves

## Decision Outcome

Chosen option: "Leave it in place", because unapplying is applying. Every write
to the transformation project traces back to an operator approving those exact
contents, and there is no second write with no second approval.

This is the same stance ADR-0014 took for the drift trigger, arriving from the
other side: the component that made a change does not get to quietly unmake it.
Restoring the project is an ordinary operation on an ordinary bind mount —
discarding local changes — which is one of the reasons ADR-0003 chose a bind
mount over an opaque volume.

An operator-approved revert was rejected as scope rather than as a bad idea. It
is a coherent feature and it needs its own proposal, its own state, and its own
place in the interface; inventing it here would be building an unrequested
capability inside a change about applying one.

## Consequences

- Good, because the invariant stays absolute and easy to state: the agent writes
  to the transformation project only what an operator approved.
- Good, because there is no code path that modifies the project without a
  decision, so the claim can be checked by reading the routing rather than by
  reasoning about when a revert would fire.
- Good, because resetting is a checkout, which is already how the stack is reset
  between rehearsals.
- Bad, because a failed verification leaves the machine in a modified state, and
  a rehearsal that skips the reset begins from the wrong place. This belongs in
  the runbook rather than in the agent.
- Bad, because the operator has no in-product way to undo an applied fix; they
  drop to the filesystem. Acceptable for a single-operator local demo, and a
  clear extension point if it ever stops being one.
