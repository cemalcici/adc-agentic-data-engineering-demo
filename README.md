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

- **[adr/](adr/)** — twenty-nine decision records, each with the alternatives
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

## LLM-as-Judge

After dbt validation, `judge_proposal` reviews the column-rename fix using a
separate model. It first assesses raw evidence without the producer's diagnosis
or SQL proposal, then reviews the exact proposal against that assessment.
Problem alignment, correction adequacy, and preservation of existing behavior
are shown with reasons and evidence. The human records both approval/rejection
and agreement/partial agreement/disagreement with the judge (optional note).
Judge findings never trigger retries or approval. Each judge call has a 30-second
request timeout and no SDK retries; failures appear as an unavailable review and
the human may still decide. This is advisory review, not proof of data accuracy.

Set `JUDGE_MODEL` in `.env` to an accessible model different from `OPENAI_MODEL`.
Optional `JUDGE_BASE_URL` and `JUDGE_API_KEY` reuse the producer settings when empty.
Model IDs are shown on the proposal and retained with the incident's review.
No judge model is silently selected for you.

For an existing database, apply the additive migration before starting updated
agent/console services (no data reset needed):

```bash
docker compose exec -T postgres bash /docker-entrypoint-initdb.d/05-judge-review.sh
docker compose up -d --build agent streamlit
```

Fresh databases run this migration automatically during initialization.

Focused tests, using an environment with the agent and console requirements:

```bash
python -m pytest tests -q
```
