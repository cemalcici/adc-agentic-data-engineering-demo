# Carry proposed fixes as file contents

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

The agent proposes a change to a model file. The operator reviews it and either
approves it or does not. If they approve, something writes the change.

The natural artefact for reviewing a change is a difference — it is what code
review shows, and what the underlying report has in mind when it describes
reviewing an agent's output like a junior engineer's pull request. The question
is whether the difference is also the right thing to *store*.

The project has more than one model since ADR-0008, so a proposal also has to
say which file it applies to.

## Considered Options

- Store the target file's path and its full contents before and after; derive
  the difference for display
- Store the target file's path and a difference between the two
- Store both the contents and a precomputed difference

## Decision Outcome

Chosen option: "Store the contents", because it makes one class of mistake
impossible. The operator approves what is on the screen. If the record held a
difference, what actually gets written is the result of applying that difference
to whatever the file contains at that moment — and if the file has moved on, the
approved thing and the written thing are not the same thing. Storing the result
means they cannot diverge, whatever else goes wrong.

The difference is still what the operator sees; it is derived from the two
contents rather than stored beside them. That is the right direction of
derivation: a difference is an excellent way to *show* a change and a poor way
to *carry* one.

It also costs nothing. The agent validates its candidate by compiling it, so the
complete after-contents already exist at the moment a proposal is recorded.

Storing both was rejected: the same information twice, free to disagree, in the
one record whose purpose is to be unambiguous about what was approved.

## Consequences

- Good, because what the operator approved and what gets written are the same
  bytes, structurally rather than by care.
- Good, because applying a fix is a write rather than a patch, so it has no
  failure mode of its own.
- Good, because the record is self-contained: an incident read back later shows
  exactly what the file looked like on both sides of the change, without needing
  the repository at that revision.
- Bad, because the record stores whole file snapshots. Negligible for a model of
  a few dozen lines, and it would not be for a large one.
- Bad, because a fix silently overwrites anything else that changed in that file
  meanwhile, rather than failing the way applying a stale difference would. In
  this system only the agent writes there, so nothing else should be changing
  it — but that is an argument from scope, not from the mechanism.
