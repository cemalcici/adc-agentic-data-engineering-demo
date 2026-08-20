"""Proving a candidate builds, before anyone is asked about it.

A proposal that is approved and then fails is worse than no proposal. So a
candidate is built first — the whole project, against the landing table the
pipeline actually reads, with the same dbt the pipeline runs, on a copy that is
not the transformation project and into schemas nothing looks at.

Parsing would not do. The staging layer is a view, and a view reading a column
that does not exist parses cleanly and fails when it is created, which is the
entire error class this system exists to catch.

See adr/0022-prove-a-fix-by-building-it-on-a-copy.md
See adr/0008-transform-through-a-staging-view-into-a-mart-table.md
"""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
from dataclasses import dataclass

import psycopg2
import sandbox

ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")

# dbt writes these itself; copying them in would carry one run's artefacts into
# the next validation. `logs` additionally arrives owned by the orchestrator.
NOT_COPIED = shutil.ignore_patterns("target", "logs", "dbt_packages", ".user.yml")

# How much of a failed build to keep. Enough for the model to see which model
# failed and what the database said; dbt's summary is at the end, so the tail is
# the part worth keeping.
FAILURE_OUTPUT_LIMIT = 6000

# Every model configures a schema, so this replaces the project's own macro in
# the copy. Same logic, one prefix — which is what keeps a validation build out
# of the schemas the pipeline writes.
SCHEMA_MACRO = """\
{#
    Written by the agent into its copy of the project, replacing the project's
    own macro for the duration of one validation build.

    The logic is the project's, with a prefix in front of it: a validation build
    must exercise the same lineage the pipeline does while writing nowhere the
    pipeline reads. The prefix is what makes the resulting schemas recognisable
    as the agent's and safe to drop.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        __PREFIX__{{ target.schema }}
    {%- else -%}
        __PREFIX__{{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
"""

DROP_VALIDATION_SCHEMAS = """
    SELECT nspname FROM pg_namespace WHERE nspname LIKE %s
"""


@dataclass(frozen=True)
class ValidationResult:
    """What happened when a candidate was built."""

    built: bool
    output: str


class Validator:
    """Builds candidates on a copy, and leaves nothing behind."""

    def __init__(
        self,
        project_dir: str,
        scratch_dir: str,
        dbt_executable: str,
        schema_prefix: str,
        warehouse: dict[str, str],
    ) -> None:
        self._project_dir = project_dir
        self._copy = pathlib.Path(scratch_dir) / "candidate-project"
        self._dbt = dbt_executable
        self._prefix = schema_prefix
        self._warehouse = warehouse

    # -- the working copy ----------------------------------------------------

    def _make_copy(self) -> None:
        """A fresh copy for every attempt, so nothing carries over."""
        if self._copy.exists():
            shutil.rmtree(self._copy)
        shutil.copytree(self._project_dir, self._copy, ignore=NOT_COPIED)
        macro = self._copy / "macros" / "generate_schema_name.sql"
        macro.write_text(SCHEMA_MACRO.replace("__PREFIX__", self._prefix))

    # -- the throwaway schemas ----------------------------------------------

    def drop_validation_schemas(self) -> list[str]:
        """Remove every schema this validator could have created.

        Run before a build as well as after one: a crash between building and
        dropping would otherwise leave a schema behind that the next build would
        write into.
        """
        connection = psycopg2.connect(**self._warehouse)
        try:
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute(DROP_VALIDATION_SCHEMAS, (f"{self._prefix}%",))
                schemas = [str(name) for (name,) in cursor.fetchall()]
                for schema in schemas:
                    cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            return schemas
        finally:
            connection.close()

    # -- the build -----------------------------------------------------------

    def validate(self, relative_path: str, candidate_sql: str) -> ValidationResult:
        """Build the whole project with this candidate in place of one model."""
        self.drop_validation_schemas()
        self._make_copy()

        # Checked against the copy for the same reason it is checked against the
        # real project: the guard is on the agent's path handling, and the copy
        # is where the write actually happens.
        target = sandbox.resolve_target(str(self._copy), relative_path)
        target.write_text(candidate_sql)

        try:
            completed = subprocess.run(
                [
                    self._dbt,
                    "run",
                    "--project-dir",
                    str(self._copy),
                    "--profiles-dir",
                    str(self._copy),
                    "--no-use-colors",
                ],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            output = ANSI_ESCAPE.sub("", completed.stdout + completed.stderr)
            built = completed.returncode == 0
        except subprocess.TimeoutExpired:
            output = "the validation build did not finish within 300 seconds"
            built = False
        finally:
            self.drop_validation_schemas()

        return ValidationResult(built=built, output=output[-FAILURE_OUTPUT_LIMIT:])
