# Extract by mirroring the source catalogue

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

ADR-0001 put the source and the warehouse in separate databases, so rows have to
be physically copied between them before anything can transform them. How that
copy treats the source's shape is not a detail: it decides where an upstream
column rename surfaces, and the entire demo is built on that rename reaching the
transformation intact.

An extract that names the columns it expects breaks first, before the
transformation ever runs. The failure would then be attributed to extraction,
the transformation would never be reached, and the model the agent is supposed
to diagnose and repair would never be implicated.

## Considered Options

- Read the source's columns from the database catalogue at run time, rebuild the
  landing table to match, and stream rows across with bulk copy
- Expose the source through a foreign-data wrapper and select from it
- Query the source through a cross-database link

## Decision Outcome

Chosen option: "Mirror the catalogue and rebuild the landing table", because it
is the only option in which the extract holds no opinion about the schema at
all. It never writes a column name, so there is nothing in it that a rename can
contradict, and whatever the upstream looks like at that moment is what lands.

A foreign-data wrapper would make the copy a single statement, but the foreign
table's definition pins the columns, so schema-agnosticism would have to be
reconstructed by re-importing the foreign schema on every run — the same work,
plus an extension and a user mapping. A cross-database link is worse: it
requires declaring the result's columns on every query, which is the opposite of
what is needed here.

The landing table is rebuilt on every run rather than only when the shape
changes. One code path behaves the same way every time, which matters in the
part of the pipeline whose failure everything downstream is designed around.

## Consequences

- Good, because an upstream rename passes through extraction untouched and
  breaks the transformation, which is where the demo needs the failure and where
  a named model can be blamed for it.
- Good, because the extract needs no database extension, no additional
  privileges, and no configuration describing the source's shape.
- Good, because there is one code path, so a failure in extraction cannot be
  explained by having taken a different branch.
- Bad, because rebuilding the landing table drops whatever depends on it. The
  staging view is destroyed and recreated on every run, so it is briefly absent
  mid-run and, after a failed run, absent entirely. Anything inspecting the
  warehouse to understand a failure will find it missing rather than stale.
- Bad, because full replacement does not scale. It is correct for a
  demonstration dataset and wrong as a pattern to copy.
- Bad, because the landing table now has two possible writers — this extract and
  the transformation project's verification fixture. Nothing structurally
  prevents both being used; the source declaration remains the contract each
  satisfies.
