# The agent chooses contents, never targets

## Status

Accepted

## Date

2026-08-18

## Context and Problem Statement

The agent asks a language model for a corrected transformation. The obvious
shape for that request is "here is a broken project, tell me what to change" —
the model returns a file to write and what to write into it.

That shape creates a decision nobody wants to have to make. A model free to
nominate a file can nominate one it should never touch, and the system then has
to decide what to do about that: refuse and retry, refuse and give up, or
refuse and explain. Each of those is a policy about a situation that should not
be reachable.

The write scope is not incidental here. ADR-0003 gives the agent access to the
transformation project specifically so that it can repair one thing, and the
demo's whole argument is that an agent acting on a system is safe because its
reach is bounded.

## Considered Options

- Determine the target from the diagnosis and ask the model only what that file
  should contain
- Let the model return both a target and contents, and validate the target
- Let the model return both, but treat an out-of-scope target as an immediate
  failure

## Decision Outcome

Chosen option: "Determine the target, ask only for contents", because it removes
the possibility rather than guarding against it. The diagnosis already names the
transformation that failed — it comes from the build output, which states the
file path — so the target is known before the model is asked anything. A model
asked only what a known file should contain has no way to express nominating a
different one.

The whitelist refusal stays regardless. With the model unable to nominate a
target, what it now guards is the agent's own path handling. That is worth
guarding precisely because it now looks safe: the remaining way to write the
wrong file is a bug in code nobody is suspicious of.

The alternatives were both rejected for the same reason: they accept the
possibility in order to manage it, and managing it requires answering a question
— what should happen when a model tries to escape its sandbox — that this system
does not need to have an answer to.

## Consequences

- Good, because there is no path by which the model can name a file outside its
  scope, so no policy is needed for when it does.
- Good, because the request to the model is narrower, which makes its output
  easier to constrain and to check.
- Good, because the defence that remains is aimed at where a mistake could
  actually originate.
- Bad, because the model cannot tell the system it is fixing the wrong file. If
  the diagnosis identified the wrong transformation, the correction will be
  applied to it confidently, and only the operator will notice.
- Bad, because it assumes the diagnosis's file path is reliable. It comes from
  the build output rather than from the model's judgement, which is why this is
  acceptable — but it is an assumption, and it would not hold if the failure
  output stopped naming paths.
