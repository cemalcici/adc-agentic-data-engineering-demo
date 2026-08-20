"""Shared database helpers for the seeder and the arrivals loop.

Nothing here names a column of the source table. The upstream system may rename
its own identifier field — that is the demo's opening move — and its own writer
migrates with it rather than failing. The shape is read from the catalogue at
run time instead.

See adr/0013-the-simulated-upstream-migrates-as-a-whole.md
"""

from __future__ import annotations

import io
import os

import psycopg2
from psycopg2 import sql

SOURCE_TABLE = "customers"

# Columns in their declared order. The rename keeps a column's position, so a
# row built for the original shape still lines up after one.
COLUMN_QUERY = """
    SELECT a.attname
    FROM pg_attribute a
    JOIN pg_class c ON c.oid = a.attrelid
    WHERE c.relname = %s
      AND a.attnum > 0
      AND NOT a.attisdropped
    ORDER BY a.attnum
"""

# The primary key says what identifies a record. Position would only say how the
# table happened to be written.
IDENTIFIER_QUERY = """
    SELECT a.attname
    FROM pg_index i
    JOIN pg_class c ON c.oid = i.indrelid
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey)
    WHERE c.relname = %s
      AND i.indisprimary
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


def source_columns(connection: psycopg2.extensions.connection) -> list[str]:
    """Read the source table's columns, in order, as they are named right now."""
    with connection.cursor() as cursor:
        cursor.execute(COLUMN_QUERY, (SOURCE_TABLE,))
        columns = [name for (name,) in cursor.fetchall()]
    if not columns:
        raise RuntimeError(f"source table {SOURCE_TABLE} has no columns or does not exist")
    return columns


def identifier_column(connection: psycopg2.extensions.connection) -> str:
    """Read the name of the column that identifies a record."""
    with connection.cursor() as cursor:
        cursor.execute(IDENTIFIER_QUERY, (SOURCE_TABLE,))
        row = cursor.fetchone()
    if row is None:
        raise RuntimeError(f"source table {SOURCE_TABLE} has no primary key")
    return str(row[0])


def row_count(connection: psycopg2.extensions.connection) -> int:
    """Count the customer records currently in the source."""
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(SOURCE_TABLE))
        )
        return int(cursor.fetchone()[0])


def max_identifier(connection: psycopg2.extensions.connection) -> int:
    """Return the highest identifier in use, or zero when the table is empty."""
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL("SELECT coalesce(max({}), 0) FROM {}").format(
                sql.Identifier(identifier_column(connection)),
                sql.Identifier(SOURCE_TABLE),
            )
        )
        return int(cursor.fetchone()[0])


def copy_rows(connection: psycopg2.extensions.connection, rows: io.StringIO) -> None:
    """Append rows to the source table via bulk copy, using its current shape."""
    columns = source_columns(connection)
    statement = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv)").format(
        sql.Identifier(SOURCE_TABLE),
        sql.SQL(", ").join(sql.Identifier(name) for name in columns),
    )
    with connection.cursor() as cursor:
        cursor.copy_expert(statement.as_string(cursor), rows)
    connection.commit()
