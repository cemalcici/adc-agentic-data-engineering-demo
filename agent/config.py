"""Configuration, read once from the environment.

The language model is reached through an OpenAI-compatible endpoint. The
`OPENAI_` prefix names the protocol rather than the supplier — it is kept
because that is what OpenAI-compatible clients read by convention.

See adr/0018-depend-on-an-openai-compatible-endpoint-not-a-vendor.md
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
    """Everything the agent needs to know about where things are."""

    postgres_host: str
    postgres_user: str
    postgres_password: str
    source_db: str
    warehouse_db: str

    airflow_url: str
    airflow_username: str
    airflow_password: str
    dag_id: str

    dbt_project_dir: str

    # Where a candidate is built. The copy and the schemas it writes into are
    # both named for the agent, so that anything left behind by a crash is
    # recognisable as the agent's rather than the pipeline's.
    # See adr/0022-prove-a-fix-by-building-it-on-a-copy.md
    dbt_executable: str
    scratch_dir: str
    validation_schema_prefix: str

    # One attempt plus the two retries the self-correction is bounded to.
    max_fix_attempts: int

    # How long a verifying run may take before the incident concludes without
    # it. The record permits one incident in flight, so a run that never
    # finishes would otherwise hold that place and stop the agent noticing
    # anything again — a stuck pipeline becoming a stuck agent.
    # Measured from when the run was queued, which covers a run that never
    # starts as well as one that never ends.
    verification_timeout_seconds: int

    llm_base_url: str
    llm_api_key: str
    llm_model: str

    poll_interval_seconds: int
    phoenix_endpoint: str
    phoenix_ui_url: str


def load() -> Settings:
    """Read settings from the environment, failing loudly on anything missing."""
    return Settings(
        postgres_host=_require("POSTGRES_HOST"),
        postgres_user=_require("POSTGRES_USER"),
        postgres_password=_require("POSTGRES_PASSWORD"),
        source_db=_require("POSTGRES_SOURCE_DB"),
        warehouse_db=_require("POSTGRES_WAREHOUSE_DB"),
        airflow_url=_require("AIRFLOW_API_URL"),
        airflow_username=_require("AIRFLOW_ADMIN_USERNAME"),
        airflow_password=_require("AIRFLOW_ADMIN_PASSWORD"),
        dag_id=os.environ.get("AIRFLOW_DAG_ID", "customer_elt"),
        dbt_project_dir=os.environ.get("DBT_PROJECT_DIR", "/dbt"),
        dbt_executable=os.environ.get("DBT_EXECUTABLE", "/opt/dbt-venv/bin/dbt"),
        scratch_dir=os.environ.get("AGENT_SCRATCH_DIR", "/agent-scratch"),
        validation_schema_prefix=os.environ.get(
            "AGENT_VALIDATION_SCHEMA_PREFIX", "agent_validation_"
        ),
        max_fix_attempts=int(os.environ.get("AGENT_MAX_FIX_ATTEMPTS", "3")),
        # A run here takes seconds, so this is generous by an order of
        # magnitude and still short enough that a demo does not stall on it.
        verification_timeout_seconds=int(
            os.environ.get("AGENT_VERIFICATION_TIMEOUT_SECONDS", "300")
        ),
        llm_base_url=_require("OPENAI_BASE_URL"),
        llm_api_key=_require("OPENAI_API_KEY"),
        llm_model=_require("OPENAI_MODEL"),
        poll_interval_seconds=int(os.environ.get("AGENT_POLL_INTERVAL_SECONDS", "20")),
        phoenix_endpoint=os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", ""),
        # Where an operator reaches Phoenix, which is not where the agent
        # exports to: one is a browser on the host, the other a service name.
        phoenix_ui_url=os.environ.get("PHOENIX_UI_URL", ""),
    )
