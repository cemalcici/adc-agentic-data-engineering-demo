# Diagnoses carry structured fields alongside prose

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

A diagnosis has two audiences. An operator reads it and decides whether the
agent has understood the problem. The next stage of the agent uses it to build a
fix, and needs particular facts out of it: which transformation broke, which
field it expected, what replaced that field.

Prose serves the first audience and not the second. Extracting facts from it
later means either parsing English or asking the model the same question twice.

There is also a verification problem in this change itself. Its central claim is
that the agent identifies what changed, and if the output is prose then checking
that claim means reading the text and forming an opinion.

## Considered Options

- Return structured fields with a prose explanation among them
- Return prose only, and extract or re-ask for facts later
- Return structured fields only, and compose an explanation from them for display

## Decision Outcome

Chosen option: "Structured fields with prose among them", because both audiences
get what they need from one request, and the model is producing the reasoning
either way.

The decisive argument is verification. "The explanation names the renamed
column" is a judgement about wording that a person has to make. "The
expected-field value equals `customer_id`" is an assertion a test makes. This
change's central claim becomes measurable rather than eyeballed, and it stays
measurable as prompts and models change.

Prose-only was rejected because the cost lands on the next change, which would
have to re-derive facts the model already knew. Structured-only was rejected
because the explanation an operator reads would then be assembled from fields by
code, and the demo's most human moment — the agent saying what it thinks
happened — would read like a form.

## Consequences

- Good, because this change's claims can be tested rather than reviewed.
- Good, because the next stage receives facts directly and needs no second
  request to the model.
- Good, because the operator still reads something written to be read.
- Bad, because it depends on the endpoint supporting structured responses, which
  compatibility across providers does not guarantee. A provider without it needs
  a fallback that does not exist.
- Bad, because a schema constrains what the model can say. A failure that does
  not fit the fields will be forced into them, and the prose may end up
  describing something the fields contradict.
