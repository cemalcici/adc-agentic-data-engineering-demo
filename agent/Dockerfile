# The agent: watches for a failed pipeline run, explains it, proposes a
# correction, and proves that correction builds before offering it. It still
# writes nothing but the incident record.
#
# It reaches its dependencies through ordinary client libraries rather than MCP
# servers — see adr/0019-reach-tools-through-direct-clients-rather-than-mcp.md
#
# dbt is installed here too, because proving a fix means building it and the
# agent is not where dbt lived. It goes into its own virtualenv, isolated from
# the agent's own dependencies exactly as it is in the orchestrator's image, and
# its versions come from the same repository-root pin so the two installations
# cannot disagree about what a build means.
# See adr/0022-prove-a-fix-by-building-it-on-a-copy.md
#
# Built from the repository root so that shared file is reachable:
#   docker build -f agent/Dockerfile .

FROM python:3.12-slim

WORKDIR /app

COPY agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dbt-requirements.txt /tmp/dbt-requirements.txt
RUN python -m venv /opt/dbt-venv \
    && /opt/dbt-venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/dbt-venv/bin/pip install --no-cache-dir -r /tmp/dbt-requirements.txt \
    && rm /tmp/dbt-requirements.txt

# The agent's working space. A candidate is built here, on a copy of the
# transformation project — never in the project itself.
RUN mkdir -p /agent-scratch

COPY agent/*.py ./

CMD ["python", "-u", "main.py"]
