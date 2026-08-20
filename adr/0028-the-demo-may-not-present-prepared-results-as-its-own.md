# The demo may not present prepared results as its own

## Status

Accepted

## Date

2026-08-19

## Context and Problem Statement

The demo depends on a language model reached over the internet. It can be slow,
it can return something unusable, and it does this in front of an audience or
not at all — the failure mode is entirely a matter of timing.

The obvious insurance is a rescue path: a command that writes a known-good
incident into the record, so the console shows a diagnosis and a proposal and
the demo continues. It is cheap to build. It was in fact done by hand several
times while developing the console, so the mechanism already exists in
substance.

That is what makes it worth deciding rather than assuming. The rescue works
precisely because the screen looks identical either way — the record is the
channel, so an incident written by hand is indistinguishable from one the agent
produced. A presenter saying "the agent diagnosed this" over a prepared row
would be making a false statement, in a presentation whose subject is whether
systems like this can be trusted with production data.

## Considered Options

- Fall back to a recording made earlier, which cannot be mistaken for the live
  system
- Build a rescue command that seeds a prepared incident, and rely on the
  presenter to disclose it when used
- Build no fallback and retry in front of the audience

## Decision Outcome

Chosen option: "Fall back to a recording", and build no mechanism that could
present a prepared result as the system's own.

The disclosure-based option was rejected on where it puts the safeguard.
It works only while a person under pressure remembers to say a sentence that
weakens their own demonstration, at the moment they least want to. That is the
same shape of reasoning this project has refused everywhere else: the write
scope is a withheld mount rather than a rule about code, the approval gate is a
database constraint rather than a check, and the console's authority is a grant
rather than a habit. Applying it to the demo means the substitution should be
impossible, not discouraged.

Retrying with nothing prepared was rejected as unnecessarily brittle. The
failure is foreseeable, and being visibly ready for it argues for the system
rather than against it.

## Consequences

- Good, because nothing on screen during the demo can be something other than
  what it appears to be.
- Good, because the fallback is honest without depending on anyone's composure.
- Good, because it keeps a claim the whole presentation rests on — that these
  systems should be inspectable and their limits stated — true of the
  presentation itself.
- Bad, because the fallback has to be produced and kept current, and a stale
  recording is worse than none.
- Bad, because a recording breaks the demo's momentum in a way a seamless rescue
  would not. That cost is accepted deliberately: the seam is the point.
- Note for anyone extending this: hand-written incidents remain useful and are
  how the console was built and verified. What this forbids is a path that puts
  one in front of an audience as the agent's work.
