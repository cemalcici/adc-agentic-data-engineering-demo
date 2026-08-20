# Enforce the transformation write scope by withholding the mount

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

`architecture.md` states that the agent is the only actor allowed to modify the
dbt project, and that the agent writes a corrected model there and then
re-triggers the pipeline. For that sequence to work at all, the agent and the
orchestrator must see the same bytes with no rebuild — and for the invariant to
mean anything, some mechanism has to stop other actors writing there. Neither
the sharing mechanism nor the enforcement mechanism had been chosen, and getting
either wrong stays invisible until the change that applies an approved fix, where
it surfaces as a file that was written but never picked up.

## Considered Options

- Host bind mount, read-write for the agent and orchestrator, no mount at all for
  the drift-trigger service
- Host bind mount, read-write for the agent, read-only for the orchestrator, with
  dbt's build outputs redirected outside the project
- A named Docker volume shared between the agent and the orchestrator

## Decision Outcome

Chosen option: "Host bind mount, no mount for the drift-trigger service",
because it puts the enforcement where the actual risk is. The orchestrator has no
code that writes into the dbt project; the drift-trigger service exists
specifically to mutate things, so it is the plausible violator, and withholding
the mount makes the violation impossible rather than merely discouraged.

The read-only variant was rejected as protection against a threat that does not
exist, bought at the price of redirecting dbt's build and log output away from
its project directory — path juggling in exactly the change whose job is to make
the stack start cleanly. A named volume was rejected because it is opaque from
the host: the agent's write could not be shown as an ordinary file diff, and
resetting between rehearsals would mean deleting a volume rather than discarding
local changes.

### Consequences

- Good, because the write-scope invariant is enforced by what each service can
  reach, not by reviewing code for violations.
- Good, because the agent's edit is visible on the host as a normal file change,
  which is the live form of the "review it like a junior engineer's pull request"
  framing the demo is built around.
- Good, because resetting between rehearsals is a checkout rather than volume
  surgery.
- Bad, because the orchestrator technically retains write access it does not
  need; the invariant is enforced at the boundary that matters, not universally.
- Bad, because bind mounts expose host file ownership to the containers, and
  container users that differ from the host user can fail to write build output.
  This needs verifying on the target machine rather than assuming.
