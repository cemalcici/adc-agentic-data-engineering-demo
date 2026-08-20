# The incident record is the channel between agent and operator

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

The agent produces a diagnosis and a proposed fix; the operator reads them and
decides. Something has to carry that exchange in both directions, and the
obvious shape is a small service the interface calls.

There are two reasons not to reach for that here. The exchange is not
request-response — the agent works on its own schedule and the operator answers
whenever they answer, which is a queue of one rather than a call. And the demo
needs the interface to be buildable before the agent exists, which a direct
connection between them makes awkward.

There is also something the durable record has to do regardless: the run history
shown during the demo is an audit trail of what broke, what was proposed, and
what was decided. That has to be written down somewhere whatever the transport
is.

## Considered Options

- A shared record in the database, which both sides read and write
- An HTTP service the agent exposes and the interface calls
- A message queue between them, with the record written separately

## Decision Outcome

Chosen option: "A shared record", because the thing that must exist anyway — a
durable record of each incident — turns out to be sufficient as the channel. An
HTTP service would add a component whose only job is to relay between two
processes that both already talk to the same database, and it would still need
the record written alongside it.

It also decouples them in a way that matters for how this gets built. The
interface reads incidents; it does not care whether an agent produced them. That
is what allows it to be developed and verified against rows written by hand,
several changes before the agent exists.

A queue was rejected for the same reason as the service, with more moving parts:
the exchange has one producer, one consumer, and a state that must be durable
regardless.

## Consequences

- Good, because there is no component between the two sides to run, configure,
  or debug, and no protocol to keep in step.
- Good, because the interface can be built and verified without the agent, which
  takes it off the critical path behind three other changes.
- Good, because the audit trail and the channel are the same thing, so they
  cannot disagree about what happened.
- Good, because the approval decision is durable by construction — an operator's
  answer survives the agent restarting, which a direct call would not.
- Bad, because the agent learns about a decision by looking rather than by being
  told, so there is latency between approving and acting, bounded by how often
  it looks.
- Bad, because both sides now depend on the same schema, and changing it means
  changing both. A relay would have allowed them to differ.
- Bad, because nothing structurally stops the interface writing fields that are
  the agent's to write. The division is a convention here, not a permission.
