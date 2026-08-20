# Run the orchestrator on LocalExecutor with shared metadata storage

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

The PoC needs a real Airflow 3 deployment: the agent reads task status and logs
from its REST API and triggers runs through it, so the orchestrator cannot be
simulated. But Airflow's reference deployment is built for distributed execution
— a message broker, worker processes, and its own metadata database — and this
stack already runs a database, a trace collector, an agent, and a dashboard on
one laptop that has to stay responsive during a live presentation.

A related risk pushed this decision earlier than it would otherwise land:
Airflow 3 changed its API authentication model, and the agent depends on it. Left
until the agent is built, an authentication surprise blocks that change outright.

## Considered Options

- LocalExecutor, orchestrator metadata as another database on the existing
  PostgreSQL instance, brought up with zero DAGs
- CeleryExecutor following the reference deployment, with broker, workers, and a
  dedicated metadata database
- A single all-in-one standalone container

## Decision Outcome

Chosen option: "LocalExecutor with shared metadata storage", because it is a
genuine Airflow 3 deployment with the parts this PoC never exercises removed. The
demo has one DAG with two sequential tasks; distributed execution would add
containers and failure modes without changing anything the audience sees or the
agent touches.

Bringing it up before any DAG exists is deliberate. An orchestrator with no DAGs
is infrastructure, not business logic, so it does not violate the
infrastructure-before-logic split — and it forces the authentication question to
be answered while it is cheap to answer.

The standalone container was rejected because it is a development convenience:
it collapses component isolation, making diagnosis harder, and weakens the claim
that this is a real Airflow 3 deployment.

### Consequences

- Good, because the orchestrator is real without being heavy: no broker, no
  worker pool, no second database product.
- Good, because API authentication is proven working before anything depends on
  it, converting the project's highest-ranked unknown into a recorded fact.
- Bad, because LocalExecutor does not demonstrate distributed execution; anyone
  reading this deployment as a production template would be misled.
- Bad, because orchestrator metadata now shares an instance with pipeline data,
  so a database problem takes down both at once. Acceptable here because neither
  is useful without the other.
- Follow-up: record how long the API credential remains valid. Whether it expires
  determines whether the agent's client needs a refresh path, and it constrains
  how pipeline re-runs are triggered later.
