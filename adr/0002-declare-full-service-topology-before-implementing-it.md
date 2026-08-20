# Declare the full service topology before implementing it

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

`ai-workflow-rules.md` designates `docker-compose.yml` a protected file: once the
service topology is agreed and working, changes to it should be deliberate and
not a side effect of another change. The implementation plan, however, delivers
services one change at a time — the database first, then the transformation
layer, the orchestrator, the agent, and the dashboard. Those two facts pull in
opposite directions, and the first change had to resolve which one wins.

## Considered Options

- Declare every service in the first change; bring up only those that can be
  verified now
- Add each service to the compose file in the change that implements it
- Declare every service and give each a placeholder container that starts and
  does nothing

## Decision Outcome

Chosen option: "Declare every service, bring up incrementally", because it is
the only option that honours the protected-file rule. Agreeing the topology once
means a later change filling in its own service block is a deliberate act
against a settled design, which is what the rule asks for; whereas adding
services as needed would have six separate changes editing a protected file,
which is the outcome the rule exists to prevent.

Placeholder containers were rejected because they make "the stack is healthy"
ambiguous: five services that start and do nothing still appear in the process
list, and the readiness definition would have to carve them out.

### Consequences

- Good, because the shape of the system is decided once, while the whole system
  is in view, rather than accreting service by service.
- Good, because cross-service concerns that are easy to get wrong late — shared
  volumes, network names, dependency ordering — are designed together.
- Bad, because the first change is larger than its own runnable scope; it
  reasons about services whose code does not exist.
- Bad, because a declared service's definition may prove wrong when it is
  finally implemented, and correcting it will look like the very thing the rule
  discourages. The correction is legitimate; the rule targets incidental
  changes, not informed ones.
- Follow-up: services declared but not live must not report unhealthy or
  restart-loop, or an operator will read a working stack as broken.
