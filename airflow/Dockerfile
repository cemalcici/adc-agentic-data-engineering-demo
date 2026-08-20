# Orchestrator image with dbt available but isolated.
#
# dbt is installed into /opt/dbt-venv and invoked by absolute path. It shares a
# filesystem with Airflow and nothing else, so neither can force a version
# change on the other.
# See adr/0009-install-dbt-in-an-isolated-virtualenv-inside-the-orchestrator-image.md
#
# The versions come from the repository-root pin that the agent's image also
# installs from. The agent validates a candidate by building it, and a check
# using a different dbt than the pipeline runs would predict a different
# outcome — so there is one file, not one per image.
# See adr/0022-prove-a-fix-by-building-it-on-a-copy.md
#
# Built from the repository root so that shared file is reachable:
#   docker build -f airflow/Dockerfile .

FROM apache/airflow:3.3.1

USER root

COPY dbt-requirements.txt /tmp/dbt-requirements.txt

RUN python -m venv /opt/dbt-venv \
    && /opt/dbt-venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/dbt-venv/bin/pip install --no-cache-dir -r /tmp/dbt-requirements.txt \
    && chown -R airflow:0 /opt/dbt-venv \
    && rm /tmp/dbt-requirements.txt

USER airflow
