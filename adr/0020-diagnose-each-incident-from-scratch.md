# Diagnose each incident from scratch

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

The system records every incident it has ever handled: what failed, what was
diagnosed, what was proposed, and how it ended. Once a second incident occurs,
that history is available to the agent, and the accompanying report names memory
as one of the core properties of agentic behaviour.

The obvious use is recognition — the same fault recurring should be cheaper to
explain the second time. The question is whether this system should do that now.

## Considered Options

- Diagnose each incident only from current evidence, ignoring earlier ones
- Feed relevant past incidents into the diagnosis
- Reuse a past diagnosis outright when the failure looks identical

## Decision Outcome

Chosen option: "Diagnose from current evidence", because in this system ground
truth is cheap to query and assumptions are expensive to be wrong about. The
agent can read the live schema, the live model, and the actual failure output in
under a second. A remembered conclusion could save that and would be believed
without being checked.

The failure mode matters more than the saving. A remembered diagnosis that is
subtly wrong — the same column renamed differently, a similar-looking failure
with another cause — produces a confident, plausible, incorrect explanation, and
the human reviewing it has less to go on than if it had been derived freshly.
The report's own framing is that agents should query ground truth rather than
rely on assumptions, and here that is also the cheaper path.

Reusing a past diagnosis outright was rejected for the same reason, more
strongly.

This is a scope decision rather than a rejection of memory. Feeding resolved
incidents back into diagnosis is a real capability and a natural next step; it
is recorded as a future extension rather than built here.

## Consequences

- Good, because every explanation is derived from what is true now, so a
  changed situation cannot be explained by a stale conclusion.
- Good, because the agent has no accumulated state, which makes its behaviour
  reproducible: the same failure produces the same investigation.
- Good, because restarting the agent loses nothing.
- Bad, because the system does not demonstrate memory, which the accompanying
  report presents as a core agentic property. That gap is deliberate and needs a
  prepared answer rather than a silent omission.
- Bad, because a recurring fault costs the same every time, and a system that
  handled many incidents would notice patterns a human reviewer would find
  obvious.
