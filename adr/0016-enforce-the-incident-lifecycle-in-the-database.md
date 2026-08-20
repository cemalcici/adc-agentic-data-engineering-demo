# Enforce the incident lifecycle in the database

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

An incident moves through states, and only some movements make sense. Most of
them are ordinary correctness. One of them is the entire point of the system:
an incident may only become approved because an operator approved a proposal.

`architecture.md` states that exactly one place answers "has this been
approved?", and it is this record. The human-in-the-loop gate — the guardrail
the accompanying report treats as the precondition for letting an agent act at
all — is that state and nothing else.

Whatever checks that transition determines how much the gate is worth. Two
components will write to this record, and at the time of this decision neither
exists.

## Considered Options

- Constrain the states and their transitions in the schema itself
- Validate transitions in a shared module that both writers import
- Do both, with the schema as a backstop

## Decision Outcome

Chosen option: "Constrain it in the schema", because every other invariant in
this project is structural and this is the one that matters most.

The agent cannot write outside the model directory because the mount is not
there. The drift trigger cannot reach the transformation project for the same
reason. The pipeline cannot skip the gate because the graph's entry routing
reads this record. None of those depend on code being correct, which is what
makes them worth stating as invariants.

A transition check in application code would make the gate exactly as
trustworthy as two components, one of which will be written three changes from
now. In the schema, an approval can only follow a proposal regardless of what
either component gets wrong — including a component writing rows by hand, which
is precisely how the interface will be developed.

The same argument covers permitting only one in-flight incident. Because
failures are never retried away, a persistent fault produces a failed run on
every scheduled interval; without enforcement a bug could open an incident for
each, and which one an approval referred to would be genuinely ambiguous.

Doing both was rejected: the same rule in two places eventually disagrees, and
then the question is which one is right.

## Consequences

- Good, because the approval gate holds no matter what the code does, which is
  what lets it be called an invariant rather than an intention.
- Good, because rows written by hand obey the same rules as rows written by the
  agent, so developing against hand-written incidents cannot produce states the
  real system would never reach.
- Good, because the rule is written once, in the one place both consumers
  already depend on.
- Bad, because a refused write surfaces as a constraint violation rather than a
  helpful message. Naming constraints after the rules they enforce mitigates
  this; it does not remove it.
- Bad, because the lifecycle now lives in SQL, which is less familiar to read
  than the Python around it and easier to overlook when reasoning about
  behaviour.
- Bad, because changing the lifecycle later means a schema change, and this
  project only applies those on a fresh database.
