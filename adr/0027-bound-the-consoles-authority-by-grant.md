# Bound the console's authority by grant

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

ADR-0015 made the incident record the channel between the agent and the
operator's interface, with an asymmetry at its centre: the agent writes
everything except the decision, and the interface writes only the decision. That
asymmetry is the approval gate expressed as who writes what, and it is stated
out loud during the demo.

Stated is all it was. Nothing stopped the console from updating a diagnosis, a
proposed fix, or an incident's state directly — only the intention not to. The
same gap exists on the other side: the console needs to read the orchestrator to
report pipeline health, and the only credential that exists is an administrator
who can start pipeline runs.

The project has answered this shape of question three times already, and always
the same way. The transformation write scope is enforced by withholding a mount
rather than by reviewing code (ADR-0003). The incident lifecycle is enforced by
the schema rather than by whichever consumer writes it (ADR-0016). The two dbt
installations are held together by a single shared pin rather than by
remembering to update both (ADR-0022).

## Considered Options

- Give the console a database role that may read the record and update only the
  decision, and a read-only orchestrator user
- Keep one credential per system and rely on the console's code writing only
  what it should
- Have the console write decisions into a separate table the agent reads

## Decision Outcome

Chosen option: "Bound it by grant", because a claim the demo makes out loud
should be a property of the system rather than a habit of its code.

The console's database role may select from the incident record and update one
column of it. Combined with the lifecycle trigger, which already permits only
the transitions an operator is allowed to make, the console cannot write a
diagnosis, a proposed fix, or an outcome — not because it does not try, but
because it may not.

The orchestrator credential is the same decision applied where it is easier to
overlook. A console holding the administrator credential could start a pipeline
run. It never would, and "it writes only the decision" would still be false. In
a demonstration about constraining what an agent can do, what each component
*can* do is the interesting claim.

A separate decisions table was rejected outright. It gives the same isolation
and creates a second place that answers "has this been approved?", which is
precisely what the single-source rule for approval state forbids.

## Consequences

- Good, because "the interface writes only the decision" becomes checkable by
  reading a grant instead of auditing an application.
- Good, because a later edit to the console cannot widen its reach by accident;
  widening it takes a deliberate change to a privilege.
- Good, because it holds for rows written by hand and for any future consumer
  connecting with the same role.
- Bad, because the stack now carries five credentials where it began with one,
  and each is another placeholder in the example environment and another thing a
  cold start must provision.
- Bad, because the role is created by an initialisation script, so adopting it
  requires starting from an empty volume rather than adding it in place.
- Bad, because a permission failure surfaces as a database error rather than as
  a considered message, if the console is ever wrong about what it may do.
