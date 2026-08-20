# The drift trigger: introduces the upstream schema change on demand.
#
# Deliberately has no view of the transformation project — see
# adr/0003-enforce-the-transformation-write-scope-by-withholding-the-mount.md.
# Do not add a /dbt mount to this service.

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY drift.py .

CMD ["python", "-u", "drift.py"]
