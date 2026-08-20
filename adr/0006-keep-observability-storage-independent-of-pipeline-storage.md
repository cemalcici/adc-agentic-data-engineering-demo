# Keep observability storage independent of pipeline storage

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

The PoC collects agent traces — the span tree, prompts, responses, token counts,
and cost for each incident — in a self-hosted trace collector, so that the demo
can answer "how did the agent arrive at that?" and show what the reasoning cost.
`architecture.md` states as an invariant that observability is never on the
critical path: if the collector is unavailable, the agent must continue to work
unaffected.

The collector supports either its own embedded database or an external
PostgreSQL. Pointing it at the instance the pipeline already runs would avoid a
second storage mechanism, and an earlier draft of `architecture.md` said it
would. That draft was written before the invariant's implications were examined.

## Considered Options

- The collector's own embedded database on a dedicated volume
- The existing PostgreSQL instance, as an additional database
- No persistence; traces held only in memory

## Decision Outcome

Chosen option: "The collector's own embedded database on a dedicated volume",
because sharing storage would couple observability to the pipeline at exactly
the layer the invariant separates. If both live in the same database, a database
problem degrades the traces an operator would be using to diagnose that problem,
and trace history cannot be reset between rehearsals without touching pipeline
state.

In-memory was rejected because the stack is likely to restart between a
rehearsal and the performance, and losing every prior incident's trace at that
moment is precisely when it hurts.

This decision reverses an earlier statement in `architecture.md`; that file has
been corrected. No prior ADR is superseded, because none existed.

### Consequences

- Good, because the invariant holds literally: observability and the pipeline
  share no storage dependency, so neither can degrade the other through it.
- Good, because trace history can be discarded independently, which matters
  between a rehearsal and a performance.
- Good, because traces survive a restart of the collector.
- Bad, because the stack now carries two storage technologies and two backup
  concerns instead of one.
- Bad, because the embedded database is not built for high write volume; fine at
  the scale of one agent resolving occasional incidents, and a constraint to
  revisit if the agent's trace volume ever grows.
