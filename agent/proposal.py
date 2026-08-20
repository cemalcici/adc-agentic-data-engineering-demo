"""Asking the model what a known file should contain.

Not which file to change — that is settled before the model is involved, from
the build output that named it. A model asked only for contents has no way to
nominate a file it should never touch, so there is no policy here for when it
tries.

See adr/0023-the-agent-chooses-contents-never-targets.md
"""

from __future__ import annotations

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from diagnosis import Diagnosis


class Candidate(BaseModel):
    """A proposed replacement for one transformation."""

    model_sql: str = Field(
        description=(
            "the complete new contents of the file, from its first line to its "
            "last, ready to be written over the existing one"
        )
    )
    summary: str = Field(
        description="one sentence naming what was changed and why, for an operator"
    )


PROMPT = """\
A data pipeline is failing because an upstream source renamed a field. You have
already diagnosed it. Now write the corrected transformation.

What you concluded:
{explanation}

The field the transformation expected: {expected_field}
The field that replaced it upstream: {replacing_field}

The columns the upstream source has right now:
{source_columns}

The file to correct is {model_path}. Its current contents:
{model_sql}

Return the complete corrected contents of that file.

Change only what the fault requires. Keep every comment, every other column, and
the existing formatting exactly as they are — an operator is about to read the
difference between what is there now and what you return, and anything you
changed for no reason costs them time deciding whether it mattered.

Where the file reads the renamed field, read the new name and present it under
the old one, so that everything downstream of this transformation keeps working
unchanged.
{retry_context}"""

RETRY_CONTEXT = """
Your previous attempt did not build. This is what the build printed:

{build_output}

Work out what was wrong with it and return contents that build.
"""


def propose(
    client: ChatOpenAI,
    diagnosis: Diagnosis,
    model_path: str,
    model_sql: str,
    source_columns: list[str],
    previous_failure: str | None = None,
) -> Candidate:
    """Ask for the corrected file, optionally knowing why the last one failed."""
    prompt = PROMPT.format(
        explanation=diagnosis.explanation,
        expected_field=diagnosis.expected_field,
        replacing_field=diagnosis.replacing_field,
        source_columns=", ".join(source_columns),
        model_path=model_path,
        model_sql=model_sql,
        retry_context=(
            RETRY_CONTEXT.format(build_output=previous_failure)
            if previous_failure
            else ""
        ),
    )
    structured = client.with_structured_output(Candidate)
    result = structured.invoke(prompt)
    if not isinstance(result, Candidate):
        raise TypeError("the model did not return a candidate in the expected shape")
    return result
