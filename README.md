# ADC — Agentic Data Engineering

A local proof of concept: a data pipeline breaks because an upstream system
renamed a column, an agent notices, diagnoses it, proposes a fix, proves the fix
builds, and — once a person approves it — applies it and re-runs the pipeline
until it is green again.

Everything runs on one machine through Docker Compose. The only dependency
outside it is an OpenAI-compatible endpoint for the agent's reasoning.

## Running the demo

**[DEMO.md](DEMO.md)** is the runbook: how to reset, what to do and say at each
beat, how to read the trace viewer, what to do when something goes wrong, and
the questions an audience asks. It is written in Turkish, because it is a script
to be read aloud and the presentation is given in Turkish.

```bash
cp .env.example .env       # then fill in the placeholders
docker compose up -d
./verify-stack.sh          # 19 readiness assertions
```

Then open the operator console at http://localhost:8501.

## Checking it still works

```bash
./verify-stack.sh          # the stack is ready
./smoke-tests.sh           # drift breaks the pipeline; an approved fix restores it
```

Neither consults a language model. What they cannot check — whether the agent's
explanation reads well, whether the proposed change is small enough to take in —
is what a rehearsal is for.

## How it is built

- **[adr/](adr/)** — twenty-eight decision records, each with the alternatives
  that were rejected and why. The code cites them by filename wherever a choice
  is not self-evident from the line that implements it, so a comment that says
  what something does can point at the record that says why.

The behaviour specifications these were written against, and the working notes
kept while building, live in a separate development repository and are not part
of what is published here.

## The shape of it

| Piece | What it owns |
| --- | --- |
| `postgres/` | The simulated upstream system, the warehouse, and the incident record |
| `airflow/` | The pipeline: extract, then transform, every five minutes |
| `dbt/` | The transformation — and the only thing the agent may write to |
| `agent/` | Detect, diagnose, propose, prove, and — once approved — apply and verify |
| `streamlit_app/` | The operator console: reads everything, writes one decision |
| `scripts/` | The drift trigger, which breaks the pipeline on demand |
