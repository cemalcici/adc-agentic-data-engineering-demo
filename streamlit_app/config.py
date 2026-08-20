"""Configuration, read once from the environment.

Every credential here is narrower than the agent's, and that is the point rather
than an accident of setup: the database role may update one column, and the
orchestrator user may read but not start a run.

See adr/0027-bound-the-consoles-authority-by-grant.md
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"required environment variable {name} is not set")
    return value


@dataclass(frozen=True)
class Settings:
    """Everything the console needs to know about where things are."""

    postgres_host: str
    postgres_user: str
    postgres_password: str
    warehouse_db: str

    airflow_url: str
    airflow_username: str
    airflow_password: str
    dag_id: str

    refresh_seconds: int


def load() -> Settings:
    return Settings(
        postgres_host=_require("POSTGRES_HOST"),
        postgres_user=_require("POSTGRES_USER"),
        postgres_password=_require("POSTGRES_PASSWORD"),
        warehouse_db=os.environ.get("POSTGRES_WAREHOUSE_DB", "warehouse_db"),
        airflow_url=_require("AIRFLOW_API_URL"),
        airflow_username=_require("AIRFLOW_USERNAME"),
        airflow_password=_require("AIRFLOW_PASSWORD"),
        dag_id=os.environ.get("AIRFLOW_DAG_ID", "customer_elt"),
        refresh_seconds=int(os.environ.get("DASHBOARD_REFRESH_SECONDS", "5")),
    )
