"""The ELT pipeline: extract upstream rows, then build the warehouse from them.

Declarative and minimal by design. No transformation logic lives here — that is
the dbt project's job — and no diagnostic logic, which belongs to the agent.
This DAG's only responsibility relative to the agent is to fail loudly and
legibly when the transformation cannot build.

The identifiers below are a contract: the agent polls this DAG and these tasks
for status from CH6, and triggers this DAG by name from CH8.
"""

from __future__ import annotations

import datetime as dt

from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import DAG

from elt_extract import extract_customers

DAG_ID = "customer_elt"
EXTRACT_TASK_ID = "extract_customers"
TRANSFORM_TASK_ID = "dbt_run"

# dbt lives in its own virtualenv inside this image and is invoked by absolute
# path — see adr/0009-install-dbt-in-an-isolated-virtualenv-inside-the-orchestrator-image.md
DBT_COMMAND = "/opt/dbt-venv/bin/dbt run --project-dir /dbt --profiles-dir /dbt"

with DAG(
    dag_id=DAG_ID,
    description="Extract upstream customers into the warehouse and transform them",
    start_date=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
    schedule=dt.timedelta(minutes=5),
    # A first start must schedule the current interval only. Replaying every
    # interval since start_date would bury the run history under a backfill.
    catchup=False,
    # Airflow creates DAGs paused by default. A paused pipeline never runs on
    # its own, which would make "runs unattended from a cold start" untrue.
    is_paused_upon_creation=False,
    # A re-triggered run and a scheduled one arriving together would produce two
    # writers of the same landing table.
    max_active_runs=1,
    # No retries: the failure this pipeline is built to show is deterministic, so
    # retrying only delays the red state and hands an observer an intermediate
    # status to interpret.
    # See adr/0011-let-pipeline-failures-stand.md
    default_args={"retries": 0},
    tags=["elt", "poc"],
) as dag:
    extract = PythonOperator(
        task_id=EXTRACT_TASK_ID,
        python_callable=extract_customers,
    )

    transform = BashOperator(
        task_id=TRANSFORM_TASK_ID,
        bash_command=DBT_COMMAND,
    )

    extract >> transform
