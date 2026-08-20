# The official postgres image runs only .sh and .sql from its init directory and
# ships no Python, which is why seeding is a separate one-shot service rather
# than an init script.
# See adr/0005-generate-seed-data-deterministically-from-a-one-shot-service.md

FROM python:3.12-slim

WORKDIR /seed

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY customer_rows.py db.py generate_customers.py source_activity.py .

CMD ["python", "-u", "generate_customers.py"]
