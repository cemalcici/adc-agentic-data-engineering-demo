# Review column-rename proposals with an advisory judge

## Status

Accepted

## Context

The PoC repairs an upstream column rename while preserving the downstream name.
A successful dbt run proves execution but does not assess whether the diagnosis
and edit match the observed failure. A human already owns the final decision.

## Decision

Insert one `judge_proposal` node after successful validation and before recording
the proposal. Use a separately configured, different model. First assess only
raw evidence; then compare the producer diagnosis and exact candidate with that
recorded assessment. Report three checks with reasons and evidence: problem
alignment, solution adequacy, and preservation of existing behavior.

Keep both stages inside this node. Add no service, lifecycle state, judge-driven
retry, veto, or extra demo scenario. A request timeout or malformed response
records an unavailable review; it does not prevent the human deciding.

Store the review and SQL atomically on the incident. Record human agreement with
the review separately from proposal approval, in the same decision transaction.
Require feedback when a completed review exists. Extend the console's column
grants only to these human feedback fields; judge output remains agent-owned.
This extends ADR-0027's decision-only grant to decision plus human feedback.

## Consequences

Only the final buildable candidate incurs two judge calls. The independent first
assessment is not exposed to the producer's interpretation. A different model is
not a correctness guarantee; uncertainty remains visible and the human retains
responsibility. Existing databases need the additive 05-judge-review migration.
