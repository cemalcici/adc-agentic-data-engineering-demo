# Install dbt in an isolated virtualenv inside the orchestrator image

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

dbt has to run somewhere. ADR-0004 fixed the orchestrator's deployment shape and
ADR-0003 already bind-mounts the transformation project into the orchestrator's
container, so the container can see the models — but the stock orchestrator
image has no dbt in it.

Installing it is not a formality. Airflow and dbt each pin large, overlapping
dependency sets, and putting them in one Python environment is a well-known way
to end up resolving version conflicts instead of building the thing you meant to
build. Whatever is chosen also has to be invocable by a scheduled task later,
since that is how the pipeline will run it.

## Considered Options

- A dedicated virtualenv inside the orchestrator image, invoked by absolute path
- Installing dbt into the orchestrator's own Python environment
- A separate dbt container, invoked by the orchestrator through the Docker socket

## Decision Outcome

Chosen option: "A dedicated virtualenv inside the orchestrator image", because
it removes the dependency conflict entirely without adding a service. The two
tools share a filesystem and nothing else; neither can force a version change on
the other, and a scheduled task invokes dbt by absolute path exactly as an
operator does by hand.

Installing into the shared environment was rejected as a conflict waiting to
happen, at a point in the project where the cost of hitting one is a detour into
dependency resolution.

A separate container was rejected despite being the cleanest isolation: it
requires mounting the Docker socket into the orchestrator, which is a
substantial complexity and security surface to accept in a single-operator local
demo, and it would put container orchestration inside a component whose stated
job is orchestrating pipeline tasks.

## Consequences

- Good, because dbt and the orchestrator can be upgraded independently, and
  neither's dependency tree constrains the other's.
- Good, because the same invocation works by hand and from a scheduled task, so
  what is verified now is what runs later.
- Good, because no service, socket mount, or privilege escalation is added.
- Bad, because the orchestrator's image changes from a stock image to a built
  one, so cold start now includes a build the first time and the published
  image is no longer what runs.
- Bad, because dbt is invoked by absolute path rather than by name, which is
  easy to get wrong and gives no useful error when it is.
- Bad, because two Python environments live in one container, which is more to
  explain to anyone reading the image than a single environment would be.
