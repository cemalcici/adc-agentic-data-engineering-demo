"""Copy the upstream customers table into the warehouse's landing area.

The source and the warehouse are separate databases (ADR-0001), so rows must be
physically copied between them before anything can transform them.

This code names no source column anywhere. It asks the source what its columns
are at run time and reproduces exactly that, so an upstream rename lands in the
warehouse under its new name and breaks the transformation rather than being
absorbed or rejected here. That failure is what the rest of the system exists to
diagnose, and moving it into this task would put it somewhere the agent is not
permitted to fix.

See adr/0010-extract-by-mirroring-the-source-catalogue.md
"""

from __future__ import annotations

import io
import os

import psycopg2
from psycopg2 import sql

LANDING_SCHEMA = "raw"
LANDING_TABLE = "customers"
SOURCE_TABLE = "customers"
SOURCE_SCHEMA = "public"

# Columns and their exact types, straight from the catalogue. format_type gives
# the type as PostgreSQL would render it, including length and precision, so the
# landing table is a faithful copy rather than an approximation.
COLUMN_QUERY = """
    SELECT a.attname, format_type(a.atttypid, a.atttypmod)
    FROM pg_attribute a
    JOIN pg_class c ON c.oid = a.attrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = %s
      AND c.relname = %s
      AND a.attnum > 0
      AND NOT a.attisdropped
    ORDER BY a.attnum
"""


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


def _connect(database: str) -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=_require_env("POSTGRES_HOST"),
        dbname=database,
        user=_require_env("POSTGRES_USER"),
        password=_require_env("POSTGRES_PASSWORD"),
    )


def read_source_columns(
    connection: psycopg2.extensions.connection,
) -> list[tuple[str, str]]:
    """Ask the source what its columns are, right now."""
    with connection.cursor() as cursor:
        cursor.execute(COLUMN_QUERY, (SOURCE_SCHEMA, SOURCE_TABLE))
        columns = [(name, type_name) for name, type_name in cursor.fetchall()]
    if not columns:
        raise RuntimeError(
            f"source table {SOURCE_SCHEMA}.{SOURCE_TABLE} has no columns or does not exist"
        )
    return columns


def rebuild_landing_table(
    connection: psycopg2.extensions.connection,
    columns: list[tuple[str, str]],
) -> None:
    """Recreate the landing table to match whatever the source looks like.

    Rebuilt on every run rather than only when the shape changes: one code path
    behaves the same way every time, which matters in the part of the pipeline
    whose failure everything downstream is designed around.

    CASCADE is required because the transformation's staging view is built on
    this table. dbt recreates that view immediately afterwards; when it cannot —
    because the shape moved underneath it — the view stays absent and the run
    fails, which is the intended outcome.
    """
    definition = sql.SQL(", ").join(
        sql.SQL("{} {}").format(sql.Identifier(name), sql.SQL(type_name))
        for name, type_name in columns
    )
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                sql.Identifier(LANDING_SCHEMA)
            )
        )
        cursor.execute(
            sql.SQL("DROP TABLE IF EXISTS {}.{} CASCADE").format(
                sql.Identifier(LANDING_SCHEMA), sql.Identifier(LANDING_TABLE)
            )
        )
        cursor.execute(
            sql.SQL("CREATE TABLE {}.{} ({})").format(
                sql.Identifier(LANDING_SCHEMA),
                sql.Identifier(LANDING_TABLE),
                definition,
            )
        )
    connection.commit()


def copy_rows(
    source: psycopg2.extensions.connection,
    warehouse: psycopg2.extensions.connection,
) -> int:
    """Stream every source row into the landing table."""
    buffer = io.StringIO()
    with source.cursor() as cursor:
        cursor.copy_expert(
            sql.SQL("COPY {}.{} TO STDOUT WITH (FORMAT csv)")
            .format(sql.Identifier(SOURCE_SCHEMA), sql.Identifier(SOURCE_TABLE))
            .as_string(cursor),
            buffer,
        )
    buffer.seek(0)

    with warehouse.cursor() as cursor:
        cursor.copy_expert(
            sql.SQL("COPY {}.{} FROM STDIN WITH (FORMAT csv)")
            .format(sql.Identifier(LANDING_SCHEMA), sql.Identifier(LANDING_TABLE))
            .as_string(cursor),
            buffer,
        )
        cursor.execute(
            sql.SQL("SELECT count(*) FROM {}.{}").format(
                sql.Identifier(LANDING_SCHEMA), sql.Identifier(LANDING_TABLE)
            )
        )
        landed = int(cursor.fetchone()[0])
    warehouse.commit()
    return landed


def extract_customers() -> None:
    """Mirror the source table into the landing area."""
    source = _connect(_require_env("POSTGRES_SOURCE_DB"))
    warehouse = _connect(_require_env("POSTGRES_WAREHOUSE_DB"))
    try:
        columns = read_source_columns(source)
        print(f"source columns: {', '.join(name for name, _ in columns)}")

        rebuild_landing_table(warehouse, columns)
        landed = copy_rows(source, warehouse)

        print(f"landed {landed} rows into {LANDING_SCHEMA}.{LANDING_TABLE}")
    finally:
        source.close()
        warehouse.close()
