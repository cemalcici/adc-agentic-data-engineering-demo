# The operator console. Presentation and one decision.
#
# It holds no credential the agent holds: its database role may update a single
# column, and its orchestrator user may read but not start a run. Nothing here
# enforces that — the grants do, which is the point.
# See adr/0027-bound-the-consoles-authority-by-grant.md

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY .streamlit ./.streamlit
COPY *.py ./

EXPOSE 8501

CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
