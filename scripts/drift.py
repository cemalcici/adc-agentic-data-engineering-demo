"""Introduce the upstream schema change.

This is the demo's opening move: an upstream system renames a column, and the
pipeline that depends on it breaks. Packaging it as one command is what makes
the demo reproducible rather than something typed from memory in front of an
audience.

It touches the source and nothing else. It has no view of the transformation
project — that is deliberate, and it is why there is no way to undo the change
from here: without seeing whether the model has already been repaired, a
reversal could put the system into a mirror-image failure that resembles the
original and has the opposite cause.

Reset is a full teardown of the stack.

See adr/0014-the-drift-trigger-cannot-undo-itself.md
"""

from __future__ import annotations

import os
import sys

import psycopg2
from psycopg2 import sql

TABLE = "customers"
ORIGINAL_COLUMN = "customer_id"
DRIFTED_COLUMN = "cust_id"

COLUMN_EXISTS = """
    SELECT count(*)
    FROM pg_attribute a
    JOIN pg_class c ON c.oid = a.attrelid
    WHERE c.relname = %s AND a.attname = %s AND a.attnum > 0 AND NOT a.attisdropped
"""


def require_env(name: str) -> str:
    """Read a required environment variable or fail loudly."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def connect() -> psycopg2.extensions.connection:
    """Open a connection to the simulated upstream database."""
    return psycopg2.connect(
        host=require_env("POSTGRES_HOST"),
        dbname=require_env("POSTGRES_SOURCE_DB"),
        user=require_env("POSTGRES_USER"),
        password=require_env("POSTGRES_PASSWORD"),
    )


def column_exists(connection: psycopg2.extensions.connection, column: str) -> bool:
    """Ask the source whether a column is present."""
    with connection.cursor() as cursor:
        cursor.execute(COLUMN_EXISTS, (TABLE, column))
        return int(cursor.fetchone()[0]) > 0


def record_count(connection: psycopg2.extensions.connection) -> int:
    """Count the records in the source table."""
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(TABLE)))
        return int(cursor.fetchone()[0])


def rename(connection: psycopg2.extensions.connection) -> None:
    """Rename the identifier column."""
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL("ALTER TABLE {} RENAME COLUMN {} TO {}").format(
                sql.Identifier(TABLE),
                sql.Identifier(ORIGINAL_COLUMN),
                sql.Identifier(DRIFTED_COLUMN),
            )
        )
    connection.commit()


def report(connection: psycopg2.extensions.connection) -> None:
    """Confirm the change against the source itself and say what it means.

    Verified here rather than by watching the pipeline: an operator needs to
    know it worked before moving on, proving a rename landed is a question about
    the source, and answering it anywhere else would give this script knowledge
    of the orchestrator that it is deliberately kept away from.
    """
    still_there = column_exists(connection, ORIGINAL_COLUMN)
    arrived = column_exists(connection, DRIFTED_COLUMN)
    records = record_count(connection)

    print()
    print("Upstream schema change applied")
    print("------------------------------")
    print(f"  {ORIGINAL_COLUMN:<12} {'still present — UNEXPECTED' if still_there else 'gone'}")
    print(f"  {DRIFTED_COLUMN:<12} {'present' if arrived else 'MISSING — UNEXPECTED'}")
    print(f"  records carrying it: {records}")
    print()
    print("  The next pipeline run will extract this shape successfully and then")
    print("  fail at the transformation step, which still reads the old name.")
    print()
    print("  There is no way to undo this from here. Reset with:")
    print("      docker compose down -v")
    print()

    if still_there or not arrived:
        raise RuntimeError("the source is not in the expected state after renaming")


def main() -> int:
    connection = connect()
    try:
        if column_exists(connection, DRIFTED_COLUMN):
            # Easier to run this twice during a live demo than to be certain you
            # did not. Nothing is wrong, so nothing should look wrong.
            print(
                f"the upstream change is already in place: "
                f"{TABLE}.{DRIFTED_COLUMN} exists, nothing to do"
            )
            return 0

        if not column_exists(connection, ORIGINAL_COLUMN):
            raise RuntimeError(
                f"{TABLE} has neither {ORIGINAL_COLUMN} nor {DRIFTED_COLUMN}; "
                f"the source is not in a state this trigger understands"
            )

        rename(connection)
        report(connection)
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    sys.exit(main())
