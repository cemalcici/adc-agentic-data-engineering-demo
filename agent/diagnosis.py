"""Asking the model what changed.

The answer comes back as fields plus prose. The operator reads the prose;
`proposal.py` builds a fix from the fields; and the central claim — that the
agent identifies what changed — becomes something a test asserts rather than
something a person judges by reading.

See adr/0021-diagnoses-carry-structured-fields-alongside-prose.md
"""

from __future__ import annotations

from typing import Literal, TypedDict

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class Diagnosis(BaseModel):
    """What the agent concluded about a failure."""

    failing_task: str = Field(description="the pipeline step that failed")
    failing_model: str = Field(
        description="the transformation that could not be built, as its file path"
    )
    expected_field: str = Field(
        description="the field name the transformation expected and did not find"
    )
    replacing_field: str = Field(
        description="the field name that appears to have replaced it in the source"
    )
    confidence: float = Field(
        description="how confident this explanation is, from 0 to 1", ge=0.0, le=1.0
    )
    explanation: str = Field(
        description=(
            "a short explanation in plain prose, written to be read aloud to an "
            "operator deciding whether to trust it"
        )
    )


class Evidence(TypedDict):
    """Everything the model is shown."""

    failing_task: str
    failure_output: str
    model_path: str
    model_sql: str
    source_columns: list[str]


PROMPT = """\
A scheduled data pipeline has failed. You are explaining why, to a data engineer
who will decide whether to trust your explanation.

The pipeline extracts rows from an upstream source into a warehouse, then builds
transformations over them. The upstream system is outside our control and
sometimes changes its schema.

The step that failed: {failing_task}

What it printed:
{failure_output}

The transformation it was building ({model_path}):
{model_sql}

The columns the upstream source has right now:
{source_columns}

Work out which field the transformation expected, which field appears to have
replaced it upstream, and say so. Base the expected field on what the
transformation actually reads — the upstream no longer carries the old name, so
it cannot be recovered from the source column list.
"""


def build_model(base_url: str, api_key: str, model: str) -> ChatOpenAI:
    """A client for whichever OpenAI-compatible endpoint is configured."""
    return ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model,
        # The explanation should be the same one twice for the same failure; a
        # demo that reads differently on the second run invites the wrong
        # questions.
        temperature=0,
        timeout=90,
    )


def diagnose(client: ChatOpenAI, evidence: Evidence) -> Diagnosis:
    """Ask the model to explain the failure."""
    prompt = PROMPT.format(
        failing_task=evidence["failing_task"],
        failure_output=evidence["failure_output"],
        model_path=evidence["model_path"],
        model_sql=evidence["model_sql"],
        source_columns=", ".join(evidence["source_columns"]),
    )
    structured = client.with_structured_output(Diagnosis)
    result = structured.invoke(prompt)
    if not isinstance(result, Diagnosis):
        raise TypeError("the model did not return a diagnosis in the expected shape")
    return result


def check_endpoint(client: ChatOpenAI) -> tuple[Literal["ok", "unusable"], str]:
    """Ask the endpoint one trivial question, to find out now rather than later.

    Configuration that is only exercised when the agent first has work to do
    fails in front of an audience. This moves that to startup — and deliberately
    reports rather than exits, because a container that restarts on a bad
    variable drowns the demo in noise while everything else is healthy.
    """
    try:
        client.invoke("Reply with the single word: ok")
    except Exception as error:  # noqa: BLE001 - any failure here means unusable
        return "unusable", f"{type(error).__name__}: {error}"[:300]
    return "ok", "endpoint answered"
