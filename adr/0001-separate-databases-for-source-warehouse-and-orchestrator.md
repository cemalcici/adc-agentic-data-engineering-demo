# Separate databases for source, warehouse, and orchestrator metadata

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

The PoC's demo depends on the source data reading as an upstream system outside
the pipeline's control: an external actor renames a column, and the pipeline
breaks downstream. The context files were ambiguous about how that separation is
realised — `architecture.md`'s stack table called `source_db` and `warehouse_db`
"schemas", while its storage model described them as separate databases. That
ambiguity had to be settled before any initialisation SQL or dbt profile could
be written, because PostgreSQL treats the two cases very differently: schemas in
one database can be queried together, separate databases cannot.

## Considered Options

- One PostgreSQL instance, separate `source_db`, `warehouse_db`, and `airflow`
  databases
- One PostgreSQL instance, one database, with `source` and `warehouse` schemas
- Two PostgreSQL instances, one for source and one for the warehouse

## Decision Outcome

Chosen option: "One PostgreSQL instance, separate databases", because it makes
the upstream boundary structurally true rather than a naming convention.
PostgreSQL's inability to query across databases means no later change can
accidentally erase the separation the demo's narrative depends on, while a
single instance keeps the footprint appropriate for a laptop demo — the
isolation that matters here is logical, not operational.

Two instances were rejected as a container's worth of cost for isolation the
demo does not exercise. A single database with two schemas was rejected because
cross-schema access is unrestricted, so the "external upstream system" framing
would rest entirely on discipline, and it would have required rewriting the
storage model in `architecture.md`.

### Consequences

- Good, because the demo's central claim — that an upstream system changed
  underneath the pipeline — is enforced by the database engine rather than by
  convention.
- Good, because the orchestrator's metadata is isolated from pipeline data
  without adding an instance.
- Bad, because the pipeline must now physically copy rows from `source_db` into
  `warehouse_db` before any transformation, adding an extract step that a
  single-database design would not need.
- Bad, because two connection configurations exist where one would do; the agent
  will need both when it inspects the live source schema.
- Follow-up: the extract step must be schema-agnostic — propagating whatever
  columns it finds rather than naming them — so that a source column rename
  reaches the transformation layer and breaks there. If the extract names
  columns explicitly, drift breaks the extract instead, and the demo's
  requirement that the transformation step is what fails cannot be met.
