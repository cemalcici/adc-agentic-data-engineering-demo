"""Gathering what the diagnosis reasons about.

Two sources. The transformation says what the pipeline expected; the source says
what it actually got. Both are read fresh every time — see
adr/0020-diagnose-each-incident-from-scratch.md.

Reading the transformation rather than the source to learn the former column
name is not a preference. After a rename the simulated upstream carries only the
new name, so the transformation is the only place the expectation still exists.
See adr/0013-the-simulated-upstream-migrates-as-a-whole.md
"""

from __future__ import annotations

import pathlib
import re

import psycopg2

# dbt names the failing model's path in its error output, so the file never has
# to be guessed at. Measured in CH2 and confirmed through the orchestrator's API
# in CH3.
MODEL_PATH = re.compile(r"in model \w+ \((models/[^)]+\.sql)\)")

SOURCE_COLUMNS = """
    SELECT a.attname
    FROM pg_attribute a
    JOIN pg_class c ON c.oid = a.attrelid
    WHERE c.relname = %s AND a.attnum > 0 AND NOT a.attisdropped
    ORDER BY a.attnum
"""


def failing_model_path(failure_output: str) -> str | None:
    """Pull the failing model's path out of the failure output."""
    match = MODEL_PATH.search(failure_output)
    return match.group(1) if match else None


def read_model(project_dir: str, relative_path: str) -> str:
    """Read a transformation model as it currently stands on disk."""
    path = pathlib.Path(project_dir) / relative_path
    return path.read_text()


def source_columns(
    host: str, database: str, user: str, password: str, table: str = "customers"
) -> list[str]:
    """The source table's columns as they are named right now."""
    connection = psycopg2.connect(host=host, dbname=database, user=user, password=password)
    try:
        with connection.cursor() as cursor:
            cursor.execute(SOURCE_COLUMNS, (table,))
            return [str(name) for (name,) in cursor.fetchall()]
    finally:
        connection.close()
