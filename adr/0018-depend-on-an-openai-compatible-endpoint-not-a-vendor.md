# Depend on an OpenAI-compatible endpoint, not a vendor

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

The agent needs a language model. An early decision, recorded in
`progress-tracker.md` rather than as an ADR, chose the OpenAI API on the grounds
that the demo's value depends on real reasoning quality and a key was available.

The reasoning was right. The specificity was incidental, and it has become
costly. Model identifiers move faster than this repository will, the operator
running the demo may hold a key for a different provider entirely, and gateways
that aggregate several providers are now an ordinary way to work. Naming one
vendor in code buys nothing and forfeits the ability to change providers between
a rehearsal and a performance.

## Considered Options

- Talk to any OpenAI-compatible endpoint, with the address, model identifier and
  key supplied as configuration
- Keep talking to OpenAI specifically
- Abstract over several providers' native interfaces behind an internal
  interface

## Decision Outcome

Chosen option: "Any OpenAI-compatible endpoint", because the wire format has
become the thing every serious provider agrees on, which makes it a more stable
dependency than any single supplier. The code depends on a protocol; which
supplier answers is configuration.

The variables keep their `OPENAI_` prefix rather than being renamed to something
vendor-neutral. That prefix is what OpenAI-compatible clients read by
convention, so keeping it means less wiring and fewer ways to misconfigure. It
names a protocol, and the documentation says so plainly, because the name
otherwise invites exactly the wrong inference.

Writing an internal abstraction over several native interfaces was rejected as
solving a problem the ecosystem already solved, at the cost of a layer to
maintain and a place for provider quirks to hide.

## Consequences

- Good, because switching providers is an environment change rather than a code
  change, which matters when the demo may be run somewhere with a different key.
- Good, because the dependency is a widely implemented format rather than one
  supplier's availability, pricing, or naming decisions.
- Good, because a gateway can be dropped in without the agent knowing.
- Bad, because compatibility is a spectrum. Structured output and function
  calling are supported unevenly, and a provider that omits what the agent uses
  will fail in a way the configuration does not hint at.
- Bad, because the `OPENAI_` prefix now means something it does not say. Anyone
  reading the configuration without the accompanying note will reasonably assume
  the wrong supplier.
- Bad, because reasoning quality now varies with configuration, so a demo that
  worked in rehearsal can behave differently after an `.env` edit. The startup
  check catches an unreachable endpoint; it cannot catch a weaker model.
